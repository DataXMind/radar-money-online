"""Synthetic offline tests for bounded repository/README capture."""
import base64
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock

from money_trend.core import DataError
from money_trend.live_shared import LiveClient
from money_trend.live_v2_github import decode_readme, parse_repositories, run, signals


def repo(ident=1):
    return {'id': ident, 'full_name': f'TEST/repo{ident}', 'html_url': f'https://github.com/TEST/repo{ident}',
            'url': f'https://api.github.com/repos/TEST/repo{ident}', 'topics': ['stripe', 'saas'],
            'description': 'SYNTHETIC payment lead only'}


def search(items):
    return json.dumps({'total_count': len(items), 'incomplete_results': False, 'items': items}).encode()


def readme(text='SYNTHETIC Stripe pricing checkout starter', ident=1):
    raw = text.encode()
    return json.dumps({'type': 'file', 'encoding': 'base64', 'content': base64.b64encode(raw).decode(),
                       'size': len(raw), 'path': 'README.md', 'sha': 'a' * 40,
                       'url': f'https://api.github.com/repos/TEST/repo{ident}/contents/README.md?ref=main'}).encode()


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'application/json'}


class GithubV2Tests(unittest.TestCase):
    def test_recognized_empty_is_not_error_or_incomplete(self):
        self.assertEqual(parse_repositories(search([]).decode()), [])
        for doc in ({'items': []}, {'total_count': 1, 'incomplete_results': False, 'items': []},
                    {'total_count': 0, 'incomplete_results': True, 'items': []},
                    {'total_count': 0, 'incomplete_results': False, 'items': [], 'errors': ['failed']}):
            with self.subTest(doc=doc), self.assertRaises(DataError):
                parse_repositories(json.dumps(doc))

    def test_repo_identity_and_topics_validated(self):
        row = repo()
        self.assertEqual(parse_repositories(search([row]).decode())[0]['full_name'], 'TEST/repo1')
        row['html_url'] = 'https://not-approved.invalid/r'
        with self.assertRaises(DataError):
            parse_repositories(search([row]).decode())

    def test_base64_size_path_and_encoding_are_strict(self):
        doc, text = decode_readme(readme().decode())
        self.assertIn('Stripe', text)
        for field, value in [('content', '!!!'), ('size', 1), ('path', '.env'), ('encoding', 'none')]:
            altered = json.loads(readme())
            altered[field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                decode_readme(json.dumps(altered))

    def test_three_mentions_never_imply_active_or_verified_payment(self):
        result = signals('SYNTHETIC Stripe\npricing page\ncheckout flow')
        self.assertTrue(all(v['mentioned'] for v in result.values()))
        self.assertTrue(all('NOT_ACTIVE' in v['verification'] for v in result.values()))

    def test_capture_dedupes_then_reads_only_actual_readme_and_refuses_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            holder = {}
            def factory(path, **kwargs):
                self.assertEqual(kwargs['allowed_hosts'], ('api.github.com',))
                self.assertEqual(kwargs['attempts'], 1)
                client = LiveClient(path, sleeper=lambda _: None, **kwargs)
                client.opener.open = Mock(side_effect=[Response(search([repo()])) for _ in range(4)] + [Response(readme())])
                holder['client'] = client
                return client
            summary = run(root, factory)
            self.assertEqual(summary['retained_repos'], 1)
            self.assertEqual(summary['request_attempts'], 5)
            self.assertEqual(summary['readmes_captured'], 1)
            records = [json.loads(l) for l in (root / 'artifacts/live-evidence-v2/github_evidence.jsonl').read_text().splitlines()]
            self.assertFalse(records[0]['active_payment_infrastructure_verified'])
            self.assertTrue(records[0]['all_three_components_mentioned'])
            self.assertTrue(records[0]['readme']['scaffold_or_starter_mention'])
            self.assertEqual(holder['client'].opener.open.call_args.args[0].full_url,
                             'https://api.github.com/repos/TEST/repo1/readme')
            with self.assertRaises(FileExistsError):
                run(root, factory)

    def test_rate_limit_stops_source_without_other_query_or_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            holder = {}
            def factory(path, **kwargs):
                client = LiveClient(path, sleeper=lambda _: None, **kwargs)
                error = urllib.error.HTTPError('https://api.github.com/search/repositories', 403, 'SYNTHETIC limited', {}, io.BytesIO(b'{}'))
                client.opener.open = Mock(side_effect=error)
                holder['client'] = client
                return client
            summary = run(Path(temp), factory)
            self.assertEqual(summary['request_attempts'], 1)
            self.assertEqual(len(summary['errors']), 1)
            holder['client'].opener.open.assert_called_once()
            self.assertEqual(summary['retained_repos'], 0)
