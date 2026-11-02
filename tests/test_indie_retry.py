"""Synthetic fallback responses only; never contacts a source or reads secrets."""
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock

from money_trend.core import DataError
from money_trend.indie_retry import ACCEPT, PLAN, RUN, capture, report
from money_trend.indie_run import KEYWORDS
from money_trend.live_shared import LiveClient


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'application/rss+xml'}


def feed(nonempty=False):
    item = ('<item><guid>SYNTHETIC-ONLY</guid><title>AI MRR report</title>'
            '<author>TEST FOUNDER</author><description>TEST revenue claim; '
            'https://not-approved.invalid/receipt remains DATA.</description>'
            '<link>https://not-approved.invalid/post</link></item>') if nonempty else ''
    return ('<rss version="2.0"><channel><title>TEST ONLY</title>' + item + '</channel></rss>').encode()


class IndieRetryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / 'config').mkdir()
        (self.root / 'docs').mkdir()
        criteria = self.root / 'docs/evidence_criteria.md'
        criteria.write_bytes(b'SYNTHETIC policy fixture, not a real result')
        self.config_path = self.root / 'config/production_v1.json'
        config = {'criteria_file': 'docs/evidence_criteria.md',
                  'criteria_sha256': hashlib.sha256(criteria.read_bytes()).hexdigest(),
                  'limits': {'raw_items': 15, 'claims': 8, 'opportunities': 5},
                  'sources': {'indiehackers_rss': {'allowed_hosts': ['feed.indiehackers.world'],
                      'keywords': KEYWORDS, 'execution_mode': 'EXPLICIT_HUMAN_APPROVAL_PER_RUN',
                      'automatic_refresh': False, 'minimum_opportunity_tier': 'T2'}}}
        self.config_path.write_text(json.dumps(config), encoding='utf-8')
        discovery = self.root / 'artifacts/indiehackers-evidence-v1/requests/001_seed_1_e6198699.body'
        discovery.parent.mkdir(parents=True)
        discovery.write_bytes(b'<html><a href="/posts.rss">RSS</a><p>q parameter</p></html>')

    def source_config(self):
        return json.loads(self.config_path.read_text())['sources']['indiehackers_rss']

    def execute(self, responses):
        self.factory_args = None
        self.client = None

        def factory(path, **kwargs):
            self.factory_args = kwargs
            self.client = LiveClient(path, sleeper=lambda _: None, **kwargs)
            self.client.opener.open = Mock(side_effect=responses)
            return self.client

        return capture(self.root, client_factory=factory)

    def error(self, index, status=500):
        return urllib.error.HTTPError(PLAN[index]['url'], status, 'SYNTHETIC failure',
            {'Content-Type': 'text/html'}, io.BytesIO(b'<html>SYNTHETIC error only</html>'))

    def test_three_500s_are_exactly_one_attempt_each_then_unreliable_and_consumed(self):
        result = self.execute([self.error(0), self.error(1), self.error(2)])
        self.assertEqual(self.client.opener.open.call_count, 3)
        self.assertEqual([c.args[0].full_url for c in self.client.opener.open.call_args_list],
                         [q['url'] for q in PLAN])
        self.assertEqual(result['source_reliability'], 'UNRELIABLE')
        self.assertEqual(result['request_attempts'], 3)
        self.assertEqual(result['records'], [])
        self.assertEqual([r['http_status'] for r in result['outcomes']], [500, 500, 500])
        config = self.source_config()
        self.assertTrue(config['retry_exhausted'])
        self.assertFalse(config['enabled'])
        self.assertFalse(config['automatic_refresh'])
        factory = Mock()
        with self.assertRaisesRegex(DataError, 'exhausted|UNRELIABLE'):
            capture(self.root, client_factory=factory)
        factory.assert_not_called()
        requests = self.root / 'artifacts' / RUN / 'requests'
        self.assertEqual(len(list(requests.glob('*.body'))), 3)
        events = [json.loads(line) for line in (requests / 'requests.jsonl').read_text().splitlines()]
        self.assertEqual(sum(e['event'] == 'request_start' for e in events), 3)
        self.assertNotIn('retry_wait', [e['event'] for e in events])

    def test_first_nonempty_feed_stops_remaining_and_does_not_follow_links(self):
        result = self.execute([Response(feed(True))])
        self.assertEqual(self.client.opener.open.call_count, 1)
        self.assertEqual(result['request_attempts'], 1)
        self.assertEqual([r['state'] for r in result['outcomes']],
                         ['RECOGNIZED_NONEMPTY', 'NOT_RUN_AFTER_SUCCESS', 'NOT_RUN_AFTER_SUCCESS'])
        self.assertEqual(len(result['records']), 1)
        self.assertEqual(result['records'][0]['link'], 'https://not-approved.invalid/post')
        self.assertEqual(self.client.opener.open.call_args.args[0].full_url, PLAN[0]['url'])
        self.assertTrue(self.source_config()['retry_exhausted'])
        self.assertFalse(self.source_config()['automatic_refresh'])

    def test_empty_feed_then_mrr_success_is_distinct_from_http_failure(self):
        result = self.execute([Response(feed()), Response(feed(True))])
        self.assertEqual(self.client.opener.open.call_count, 2)
        self.assertEqual([r['state'] for r in result['outcomes']],
                         ['RECOGNIZED_EMPTY', 'RECOGNIZED_NONEMPTY', 'NOT_RUN_AFTER_SUCCESS'])
        self.assertEqual(result['source_reliability'], 'SINGLE_NONEMPTY_CAPTURE')
        self.assertEqual(result['outcomes'][0]['feed_entries'], 0)

    def test_html_200_is_ingress_error_and_never_success_or_genuine_empty(self):
        result = self.execute([Response(b'<html>not RSS</html>'), self.error(1), Response(feed())])
        self.assertEqual(self.client.opener.open.call_count, 3)
        self.assertEqual([r['state'] for r in result['outcomes']],
                         ['INGRESS_OR_REQUEST_ERROR', 'HTTP_ERROR', 'RECOGNIZED_EMPTY'])
        self.assertIsNone(result['outcomes'][0]['feed_entries'])
        self.assertEqual(result['source_reliability'], 'UNAVAILABLE_OR_EMPTY')
        self.assertEqual(result['records'], [])

    def test_client_scope_and_single_attempt_budget_are_explicit(self):
        self.execute([Response(feed(True))])
        self.assertEqual(self.factory_args['allowed_hosts'], ('feed.indiehackers.world',))
        self.assertEqual(self.factory_args['attempts'], 1)
        self.assertEqual(self.factory_args['max_requests'], 3)
        self.assertEqual(self.factory_args['accept'], ACCEPT)
        self.assertGreaterEqual(self.factory_args['interval'], 3)
        request = self.client.opener.open.call_args.args[0]
        self.assertIsNone(request.get_header('Authorization'))
        self.assertIsNone(request.get_header('Cookie'))

    def test_unexpected_interrupt_consumes_authorization_without_restart(self):
        with self.assertRaisesRegex(RuntimeError, 'synthetic interrupt'):
            self.execute([RuntimeError('synthetic interrupt')])
        config = self.source_config()
        self.assertTrue(config['retry_exhausted'])
        self.assertFalse(config['enabled'])
        self.assertEqual(config['reliability'], 'INTERRUPTED_REVIEW_REQUIRED')
        factory = Mock()
        with self.assertRaisesRegex(DataError, 'exhausted'):
            capture(self.root, client_factory=factory)
        factory.assert_not_called()

    def test_client_constructor_failure_consumes_authorization_and_disables_source(self):
        factory = Mock(side_effect=RuntimeError('synthetic constructor failure'))
        with self.assertRaisesRegex(RuntimeError, 'constructor failure'):
            capture(self.root, client_factory=factory)
        config = self.source_config()
        self.assertTrue(config['retry_exhausted'])
        self.assertFalse(config['enabled'])
        self.assertEqual(config['reliability'], 'INTERRUPTED_REVIEW_REQUIRED')
        factory.reset_mock()
        with self.assertRaisesRegex(DataError, 'exhausted'):
            capture(self.root, client_factory=factory)
        factory.assert_not_called()

    def report_fixture(self):
        """Synthetic PASS/15-row contracts used only in a temporary test folder."""
        self.execute([self.error(0), self.error(1), self.error(2)])
        out = self.root / 'artifacts' / RUN
        tests = out / 'offline-tests'
        tests.mkdir()
        log = tests / 'offline_tests.txt'
        log.write_bytes(b'SYNTHETIC REPORT FIXTURE ONLY; not a historical test outcome\n')
        fixture = {'status': 'PASS', 'failures': 0, 'errors': 0, 'tests_run': 1,
                   'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
                   'source_sha256': {},
                   'retry_t7_bundle_sha256': {'config/production_v1.json':
                       hashlib.sha256(self.config_path.read_bytes()).hexdigest()}}
        (tests / 'offline_tests.json').write_text(json.dumps(fixture), encoding='utf-8')
        baseline = self.root / 'artifacts/t7-baseline'
        baseline.mkdir()
        snapshot = baseline / 'snapshot_t0.jsonl'
        snapshot.write_bytes(''.join(json.dumps({'evidence_id': f'TEST{i:02d}',
            'note': 'SYNTHETIC ONLY'}) + '\n' for i in range(15)).encode())
        baseline_fixture = {'raw_count': 15, 'network_requests': 0, 't7_executed': False,
                            'artifacts_sha256': {'snapshot_t0.jsonl':
                                hashlib.sha256(snapshot.read_bytes()).hexdigest()}}
        (baseline / 'run_manifest.json').write_text(json.dumps(baseline_fixture), encoding='utf-8')
        return out

    def test_all_500_report_has_no_opportunities_verified_hashes_and_no_overwrite(self):
        out = self.report_fixture()
        result = report(self.root)
        self.assertEqual(result['status'], 'RESEARCH_DRAFT_ONLY')
        self.assertEqual(result['source_reliability'], 'UNRELIABLE')
        self.assertEqual(result['opportunities'], 0)
        self.assertEqual(result['raw_items'], 0)
        self.assertFalse(result['t7_executed'])
        self.assertEqual(result['baseline_records'], 15)
        ledger = json.loads((out / 'evidence_ledger.json').read_text())
        self.assertEqual(ledger['claims'], [])
        self.assertEqual(ledger['opportunities'], [])
        self.assertEqual((out / 'indiehackers_evidence.jsonl').read_bytes(), b'')
        self.assertEqual(len((out / 'opportunities.csv').read_text().splitlines()), 1)
        for name, digest in result['artifacts_sha256'].items():
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)
        self.assertEqual(hashlib.sha256((self.root / 'dashboard.md').read_bytes()).hexdigest(),
                         result['dashboard_sha256'])
        self.assertEqual(self.client.opener.open.call_count, 3)  # Report never asks client for data.
        with self.assertRaisesRegex(FileExistsError, 'no overwrite'):
            report(self.root)

    def test_report_rejects_tampered_raw_error_body(self):
        out = self.report_fixture()
        next((out / 'requests').glob('*.body')).write_bytes(b'TAMPERED')
        with self.assertRaisesRegex(DataError, 'raw hash/metadata mismatch'):
            report(self.root)
        self.assertFalse((out / 'run_manifest.json').exists())

    def test_report_rejects_tampered_request_log_plan(self):
        out = self.report_fixture()
        log = out / 'requests/requests.jsonl'
        events = [json.loads(line) for line in log.read_text().splitlines()]
        next(e for e in events if e['event'] == 'request_start')['url'] = 'https://not-approved.invalid/'
        log.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
        with self.assertRaisesRegex(DataError, 'count or plan mismatch'):
            report(self.root)
        self.assertFalse((out / 'run_manifest.json').exists())

    def test_report_rejects_tampered_offline_test_log_bytes(self):
        out = self.report_fixture()
        (out / 'offline-tests/offline_tests.txt').write_bytes(b'TAMPERED LOG')
        with self.assertRaisesRegex(DataError, 'byte-verified offline test report'):
            report(self.root)
        self.assertFalse((out / 'run_manifest.json').exists())

    def test_report_requires_one_ingress_per_distinct_request(self):
        out = self.report_fixture()
        log = out / 'requests/requests.jsonl'
        events = [json.loads(line) for line in log.read_text().splitlines()]
        positions = [i for i, event in enumerate(events) if event['event'] == 'data_ingress']
        events[positions[-1]] = dict(events[positions[0]])
        log.write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
        with self.assertRaisesRegex(DataError, 'count or plan mismatch'):
            report(self.root)
        self.assertFalse((out / 'run_manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
