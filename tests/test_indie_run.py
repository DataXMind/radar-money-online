"""Offline, synthetic captures only; no fixture is actual payment/revenue proof."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import Mock

from money_trend.core import DataError
from money_trend.indie_run import KEYWORDS, audit_capture, evaluate_reviewed, validate_source_config
from money_trend.live_shared import LiveClient


HOST = 'feed.indiehackers.world'


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


class IndieRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'artifacts/capture'
        self.requests = self.out / 'requests'
        self.requests.mkdir(parents=True)
        self.queries = [{'keyword': k, 'url': f'https://{HOST}/posts.rss?' + urlencode({'q': k})}
                        for k in KEYWORDS]
        self.events = []
        seed = self.capture('seed', f'https://{HOST}/', 200, b'<html>SYNTHETIC feed landing</html>')
        write_json(self.out / 'execution_protocol.json', {
            'source_host': HOST, 'queries': self.queries,
            'discovery_source': seed['raw_path'], 'discovery_sha256': seed['sha256']})

    def capture(self, name, url, status, body):
        meta = {'url': url, 'status': status, 'retrieved_at': '2026-11-02T01:00:00Z',
                'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body),
                'body_file': name + '.body', 'content_type': 'application/rss+xml',
                'error_response': status != 200, 'rate_limit': {}}
        raw = self.requests / meta['body_file']
        raw.write_bytes(body)
        write_json(self.requests / (name + '.meta.json'), meta)
        self.events.extend([{'event': 'request_start', 'request_id': name, 'url': url},
                            {'event': 'data_ingress', 'request_id': name, **meta}])
        self.write_events()
        return {**meta, 'raw_path': raw.relative_to(self.root).as_posix()}

    def write_events(self):
        (self.requests / 'requests.jsonl').write_text(
            ''.join(json.dumps(event) + '\n' for event in self.events), encoding='utf-8')

    def test_http_500_is_source_unavailable_not_recognized_empty(self):
        self.capture('query1', self.queries[0]['url'], 500, b'<html>synthetic server failure</html>')
        result = audit_capture(self.root, self.out)
        self.assertEqual(result['request_attempts'], 2)
        self.assertEqual(result['source_status'], 'SOURCE_UNAVAILABLE')
        self.assertIn('SOURCE_UNAVAILABLE_HTTP_500', result['gaps'])
        self.assertEqual(result['parsed_feed_responses'], 0)
        self.assertEqual(result['recognized_empty_urls'], [])
        self.assertEqual(result['records'], [])
        self.assertEqual(result['query_status'][0]['state'], 'FAILED')
        self.assertEqual([q['state'] for q in result['query_status'][1:]], ['NOT_RUN'] * 4)

    def test_real_empty_rss_is_recognized_empty(self):
        self.capture('query1', self.queries[0]['url'], 200,
                     b'<rss version="2.0"><channel><title>SYNTHETIC</title></channel></rss>')
        result = audit_capture(self.root, self.out)
        self.assertEqual(result['source_status'], 'AVAILABLE')
        self.assertEqual(result['parsed_feed_responses'], 1)
        self.assertEqual(result['recognized_empty_urls'], [self.queries[0]['url']])
        self.assertEqual(result['query_status'][0]['state'], 'RECOGNIZED_EMPTY')
        self.assertEqual(result['records'], [])

    def test_html_200_is_ingress_error_not_empty_rss(self):
        self.capture('query1', self.queries[0]['url'], 200, b'<html>not a feed</html>')
        result = audit_capture(self.root, self.out)
        self.assertIn('RSS_INGRESS_ERROR', result['gaps'])
        self.assertEqual(result['parsed_feed_responses'], 0)
        self.assertEqual(result['recognized_empty_urls'], [])

    def test_raw_body_hash_tampering_rejected(self):
        (self.requests / 'seed.body').write_bytes(b'tampered')
        with self.assertRaisesRegex(DataError, 'hash/size mismatch'):
            audit_capture(self.root, self.out)

    def test_ingress_log_tampering_rejected(self):
        self.events[1]['sha256'] = '0' * 64
        self.write_events()
        with self.assertRaisesRegex(DataError, 'logged ingress'):
            audit_capture(self.root, self.out)

    def test_request_to_other_domain_rejected_offline(self):
        self.events[0]['url'] = 'https://indiehackers.com/'
        self.write_events()
        with self.assertRaisesRegex(DataError, 'outside frozen query plan'):
            audit_capture(self.root, self.out)

    def reviewed_fixture(self):
        """One synthetic post explicitly names three periods; no invented source claim."""
        facts = ('TEST-PRODUCT TEST-FOUNDER MRR USD monthly '
                 '2026-07-01 2026-07-31 100 '
                 '2026-08-01 2026-08-31 200 '
                 '2026-09-01 2026-09-30 300 2026-10-02T00:00:00Z')
        body = ('<rss version="2.0"><channel><title>TEST</title><item><guid>TEST-POST</guid>'
                '<title>AI agent MRR report SYNTHETIC ONLY</title>'
                '<description>' + facts + '</description></item></channel></rss>').encode()
        self.capture('query1', self.queries[0]['url'], 200, body)
        records = audit_capture(self.root, self.out)['records']
        self.assertEqual(len(records), 1)
        row = records[0]
        points = []
        for index, (start, end, value) in enumerate((('2026-07-01', '2026-07-31', '100'),
                                                    ('2026-08-01', '2026-08-31', '200'),
                                                    ('2026-09-01', '2026-09-30', '300'))):
            point = {'product': 'TEST-PRODUCT', 'founder': 'TEST-FOUNDER', 'metric': 'MRR',
                     'currency': 'USD', 'cadence': 'monthly', 'value': value,
                     'period_start': start, 'period_end': end, 'observed_at': '2026-10-02T00:00:00Z',
                     'actual': True, 'statement_type': 'actual_revenue_report',
                     'review_status': 'CONFIRMED_SOURCE_STATEMENT', 'evidence_id': f'TEST-POINT-{index}',
                     'quote': facts, **{k: row[k] for k in ('source_url', 'raw_response_path',
                                                          'raw_response_sha256', 'raw_locator')}}
            point['field_quotes'] = {k: {'value': point[k], 'quote': point[k]} for k in (
                'product', 'founder', 'metric', 'currency', 'cadence', 'value',
                'period_start', 'period_end', 'observed_at')}
            points.append(point)
        return [{'product': 'TEST-PRODUCT', 'founder': 'TEST-FOUNDER', 'points': points}], records

    def test_three_raw_mapped_mrr_points_are_emerging_not_verified_payment(self):
        candidates, records = self.reviewed_fixture()
        result = evaluate_reviewed(candidates, records)
        self.assertEqual(len(result['claims']), 1)
        self.assertEqual(len(result['opportunities']), 1)
        opportunity = result['opportunities'][0]
        self.assertEqual((opportunity['tier'], opportunity['verdict']), ('T2', 'EMERGING'))
        self.assertFalse(opportunity['verified_payment'])
        self.assertFalse(opportunity['payment_evidence']['present'])
        self.assertFalse(opportunity['trend_evidence']['present'])

    def test_missing_raw_quote_field_mapping_or_locator_rejected(self):
        candidates, records = self.reviewed_fixture()
        mutations = [('quote', 'not present in source'), ('raw_locator', 'rss/channel/item[99]'),
                     ('raw_response_sha256', '0' * 64), ('field_quotes', {})]
        for field, value in mutations:
            altered = copy.deepcopy(candidates)
            altered[0]['points'][0][field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                evaluate_reviewed(altered, records)

    def test_quoted_field_value_must_match_normalized_field(self):
        candidates, records = self.reviewed_fixture()
        candidates[0]['points'][0]['field_quotes']['value']['value'] = '999'
        with self.assertRaisesRegex(DataError, 'missing raw field mapping: value'):
            evaluate_reviewed(candidates, records)

    def test_config_pins_approved_source_and_current_criteria(self):
        (self.root / 'docs').mkdir()
        criteria = self.root / 'docs/evidence_criteria.md'
        criteria.write_bytes(b'SYNTHETIC criteria pin')
        config = {'criteria_file': 'docs/evidence_criteria.md',
                  'criteria_sha256': hashlib.sha256(criteria.read_bytes()).hexdigest(),
                  'limits': {'raw_items': 15, 'claims': 8, 'opportunities': 5},
                  'sources': {'indiehackers_rss': {'allowed_hosts': [HOST], 'keywords': KEYWORDS,
                      'execution_mode': 'EXPLICIT_HUMAN_APPROVAL_PER_RUN',
                      'automatic_refresh': False, 'minimum_opportunity_tier': 'T2'}}}
        validate_source_config(config, self.root)
        for field, value in (('allowed_hosts', [HOST, 'indiehackers.com']),
                             ('automatic_refresh', True), ('minimum_opportunity_tier', 'T3')):
            altered = copy.deepcopy(config)
            altered['sources']['indiehackers_rss'][field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                validate_source_config(altered, self.root)
        criteria.write_bytes(b'changed policy')
        with self.assertRaisesRegex(DataError, 'criteria pin mismatch'):
            validate_source_config(config, self.root)

    def test_feed_scoped_client_never_opens_other_hosts_or_redirect_targets(self):
        client = LiveClient(self.root / 'client', allowed_hosts=[HOST])
        client.opener = Mock()
        for url in ('https://github.com/a', 'https://indiehackers.com/',
                    'https://feed.indiehackers.world.evil.test/', 'http://' + HOST + '/'):
            with self.subTest(url=url), self.assertRaises(DataError):
                client.get(url, 'test')
        client.opener.open.assert_not_called()
        default = LiveClient(self.root / 'default-client')
        default.opener = Mock()
        with self.assertRaises(DataError):
            default.get('https://' + HOST + '/', 'test')
        default.opener.open.assert_not_called()
