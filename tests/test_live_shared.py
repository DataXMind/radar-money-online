"""Offline scoped-client regressions; all HTTP responses are synthetic."""
import http.client
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError
from money_trend.live_shared import LiveClient, NoRedirect, public_url


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'application/json', 'X-RateLimit-Remaining': '9'}


class LiveClientTests(unittest.TestCase):
    def test_only_explicit_three_hosts_and_anonymous_https(self):
        for url in ('https://api.github.com/search/issues', 'https://github.com/search', 'https://hn.algolia.com/api/v1/search'):
            public_url(url)
        for url in ('https://news.ycombinator.com/item?id=1', 'https://example.com/', 'http://github.com',
                    'https://user:pass@github.com/', 'https://github.com:8443/',
                    'https://api.github.com/search?access_token=DO_NOT_SEND', 'https://github.com/#fragment'):
            with self.subTest(url=url), self.assertRaises(DataError):
                public_url(url)

    def test_source_scoped_hosts_and_redirect_refusal(self):
        with self.assertRaises(DataError):
            public_url('https://api.github.com/x', ('hn.algolia.com',))
        with self.assertRaises(DataError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://github.com')

    def test_success_saves_bytes_hash_logs_and_no_authorization(self):
        with tempfile.TemporaryDirectory() as temp:
            client = LiveClient(temp, allowed_hosts=('api.github.com',))
            with patch.object(client.opener, 'open', return_value=Response(b'{"items":[]}')) as mocked:
                body, meta = client.get('https://api.github.com/search/issues', 'q1')
            self.assertEqual(body, '{"items":[]}')
            self.assertEqual((Path(temp) / meta['body_file']).read_bytes(), body.encode())
            self.assertEqual(meta['rate_limit']['X-RateLimit-Remaining'], '9')
            request = mocked.call_args.args[0]
            self.assertIsNone(request.get_header('Authorization'))
            self.assertIsNone(request.get_header('Cookie'))
            events = [json.loads(line)['event'] for line in (Path(temp) / 'requests.jsonl').read_text().splitlines()]
            self.assertEqual(events, ['request_start', 'data_ingress'])

    def test_protocol_failure_retries_only_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            client = LiveClient(temp, sleeper=lambda _: None)
            with patch.object(client.opener, 'open', side_effect=http.client.IncompleteRead(b'', 1)) as mocked:
                with self.assertRaises(DataError):
                    client.get('https://api.github.com/search/issues', 'q1')
            self.assertEqual(mocked.call_count, 2)
            self.assertEqual(client.count, 2)

    def test_http_error_body_is_archived_and_not_treated_as_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            client = LiveClient(temp)
            error = urllib.error.HTTPError('https://api.github.com/x', 403, 'forbidden',
                                           {'Content-Type': 'application/json'}, io.BytesIO(b'{"message":"rate limited"}'))
            with patch.object(client.opener, 'open', side_effect=error) as mocked:
                with self.assertRaises(DataError):
                    client.get('https://api.github.com/x', 'q1')
            self.assertEqual(mocked.call_count, 1)
            meta = json.loads(next(Path(temp).glob('*.meta.json')).read_text())
            self.assertTrue(meta['error_response'])
            self.assertEqual(meta['status'], 403)

    def test_request_and_time_budget_stop_before_another_request(self):
        with tempfile.TemporaryDirectory() as temp:
            client = LiveClient(temp, max_requests=1, sleeper=lambda _: None)
            with patch.object(client.opener, 'open', return_value=Response(b'{}')) as mocked:
                client.get('https://api.github.com/x', 'q1')
                with self.assertRaisesRegex(DataError, 'budget'):
                    client.get('https://api.github.com/x', 'q2')
            self.assertEqual(mocked.call_count, 1)
            client = LiveClient(Path(temp) / 'deadline')
            client.deadline = 0
            with patch.object(client.opener, 'open') as mocked:
                with self.assertRaises(DataError):
                    client.get('https://hn.algolia.com/api/v1/search', 'q')
            mocked.assert_not_called()

    def test_long_retry_after_stops_without_early_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            client = LiveClient(temp, sleeper=lambda _: None)
            error = urllib.error.HTTPError('https://api.github.com/x', 429, 'limited', {'Retry-After': '30'}, io.BytesIO(b'limited'))
            with patch.object(client.opener, 'open', side_effect=error) as mocked:
                with self.assertRaisesRegex(DataError, 'cooldown'):
                    client.get('https://api.github.com/x', 'q')
            self.assertEqual(mocked.call_count, 1)
