"""Synthetic offline regressions. Never use these payloads as run evidence."""
import hashlib
import http.client
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from money_trend.core import Client, DataError, parse_github, strict_json
from money_trend.offline_tests import write_report
from money_trend.pipeline import ROOT, run
from tests.test_mvp import FIXTURE, Response, gh, passing_report


class GithubMetadataTests(unittest.TestCase):
    def test_errors_are_ingress_failure_in_both_routes_and_formats(self):
        for nested in (False, True):
            doc = json.loads(gh([], nested))
            route = doc['payload']['blackbirdSearchRoute'] if nested else doc['payload']
            route['errors'] = ['backend unavailable']
            body = json.dumps(doc)
            for value in (body, '<script type="application/json">' + body + '</script>'):
                with self.subTest(nested=nested, html=value.startswith('<')), self.assertRaisesRegex(DataError, 'source errors'):
                    parse_github(value)

    def test_wrong_or_missing_metadata_is_not_empty(self):
        for nested in (False, True):
            for field, value in [('errors', None), ('errors', {}), ('type', 'code'),
                                 ('result_count', 1), ('result_count', -1),
                                 ('result_count', True), ('result_count', '0')]:
                doc = json.loads(gh([], nested))
                route = doc['payload']['blackbirdSearchRoute'] if nested else doc['payload']
                route[field] = value
                with self.subTest(nested=nested, field=field, value=value), self.assertRaises(DataError):
                    parse_github(json.dumps(doc))
            for field in ('errors', 'type', 'result_count'):
                doc = json.loads(gh([], nested))
                route = doc['payload']['blackbirdSearchRoute'] if nested else doc['payload']
                del route[field]
                with self.subTest(nested=nested, missing=field), self.assertRaises(DataError):
                    parse_github(json.dumps(doc))

    def test_nonempty_results_cannot_exceed_total(self):
        doc = json.loads(gh([{'hl_name': 'example/demo'}]))
        doc['payload']['result_count'] = 0
        with self.assertRaisesRegex(DataError, 'result_count'):
            parse_github(json.dumps(doc))

    def test_paginated_total_can_exceed_page_length(self):
        doc = json.loads(gh([{'hl_name': 'example/demo'}], True))
        doc['payload']['blackbirdSearchRoute']['result_count'] = 100
        self.assertEqual(len(parse_github(json.dumps(doc))), 1)

    def test_outer_errors_cannot_be_hidden_by_clean_route(self):
        doc = json.loads(gh([], True))
        doc['payload']['errors'] = ['failed request']
        with self.assertRaises(DataError):
            parse_github(json.dumps(doc))

    def test_error_response_logs_ingress_failure_and_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'tests.json'
            passing_report(report)
            doc = json.loads(gh([], True))
            doc['payload']['blackbirdSearchRoute']['errors'] = ['backend unavailable']
            with patch('urllib.request.OpenerDirector.open', return_value=Response(json.dumps(doc).encode())) as mocked:
                manifest = run(Path(temp) / 'run', report)
            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(manifest['status'], 'RESEARCH_DRAFT_ONLY')
            self.assertTrue(manifest['errors'])
            self.assertEqual(manifest['opportunities'], [])
            events = [json.loads(line) for line in (Path(temp) / 'run/requests/requests.jsonl').read_text().splitlines()]
            self.assertTrue(any(e['event'] == 'validation_fail' for e in events))
            self.assertFalse(any(e['event'] == 'validation_pass' for e in events))


class ProtocolTests(unittest.TestCase):
    def test_open_protocol_errors_retry_bounded_then_publish_draft(self):
        for error in (http.client.IncompleteRead(b'partial', 10), http.client.BadStatusLine('bad status')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / 'tests.json'
                passing_report(report)
                out = Path(temp) / 'run'
                with patch('urllib.request.OpenerDirector.open', side_effect=error) as mocked, patch('time.sleep'):
                    run(out, report)
                self.assertEqual(mocked.call_count, 3)
                self.assert_draft_artifacts(out)
                events = [json.loads(line) for line in (out / 'requests/requests.jsonl').read_text().splitlines()]
                self.assertEqual(sum(e['event'] == 'request_error' for e in events), 3)

    def test_body_protocol_error_after_github_preserves_partial_evidence(self):
        index = strict_json((FIXTURE / 'sample_index.json').read_text(encoding='utf-8'))
        github = (FIXTURE / index['response']['body_file']).read_bytes()
        class BrokenBody(Response):
            def read(self, *args):
                raise http.client.IncompleteRead(b'partial', 10)
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / 'tests.json'
            passing_report(report)
            out = Path(temp) / 'run'
            with patch('urllib.request.OpenerDirector.open', side_effect=[Response(github)] + [BrokenBody(b'') for _ in range(3)]) as mocked, patch('time.sleep'):
                run(out, report)
            self.assertEqual(mocked.call_count, 4)
            self.assert_draft_artifacts(out)
            ledger = strict_json((out / 'evidence_ledger.json').read_text(encoding='utf-8'))
            self.assertEqual(len(ledger['raw_items']), 10)

    def test_orchestrator_defensively_catches_unwrapped_protocol_errors(self):
        for error in (http.client.IncompleteRead(b'', 1), http.client.BadStatusLine('bad')):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temp:
                report = Path(temp) / 'tests.json'
                passing_report(report)
                out = Path(temp) / 'run'
                with patch.object(Client, 'get', side_effect=error) as mocked:
                    run(out, report)
                self.assertEqual(mocked.call_count, 1)
                self.assert_draft_artifacts(out)

    def assert_draft_artifacts(self, out):
        manifest = strict_json((out / 'run_manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['status'], 'RESEARCH_DRAFT_ONLY')
        self.assertEqual(manifest['opportunities'], [])
        self.assertTrue(manifest['errors'])
        self.assertEqual(len((out / 'opportunities.csv').read_text().splitlines()), 1)
        self.assertTrue((out / 'AI_MONEY_TREND_BRIEF_v1.md').exists())
        self.assertEqual(strict_json((out / 'checkpoint.json').read_text())['state'], 'stopped')


class LogHashTests(unittest.TestCase):
    def test_saved_log_bytes_match_declared_hash_for_lf_and_crlf(self):
        for log in ('PASS\nUnicode: kiểm tra\n', 'PASS\r\nUnicode: kiểm tra\r\n', 'PASS\r'):
            with self.subTest(log=repr(log)), tempfile.TemporaryDirectory() as temp:
                result = unittest.TestResult()
                result.testsRun = 1  # Synthetic result to exercise report persistence only.
                write_report(temp, log, result, ROOT)
                raw = (Path(temp) / 'offline_tests.txt').read_bytes()
                declared = strict_json((Path(temp) / 'offline_tests.json').read_text())
                self.assertNotIn(b'\r', raw)
                self.assertEqual(hashlib.sha256(raw).hexdigest(), declared['log_sha256'])
