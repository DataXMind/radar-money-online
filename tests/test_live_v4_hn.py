"""Offline synthetic contracts for the bounded Show HN v4 capture.

The fixture names and URLs below are test data, not discovered products.
"""
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from money_trend.core import DataError
from money_trend.live_v4_hn import (
    baseline_audit, freeze_protocol, parse_response, public_product_url, text_urls,
)


class HNShowV4Tests(unittest.TestCase):
    def setUp(self):
        self.anchor = datetime(2026, 11, 3, 3, 33, 3, tzinfo=timezone.utc)
        self.protocol = freeze_protocol(self.anchor, self.anchor)
        self.query = self.protocol['queries'][0]

    def hit(self):
        created = self.anchor - timedelta(days=1)
        return {'objectID': '123456', 'created_at': created.isoformat(),
                'created_at_i': int(created.timestamp()), 'author': 'TEST-founder',
                '_tags': ['story', 'show_hn', 'author_TEST-founder'],
                'title': 'Show HN: SYNTHETIC AI tool',
                'story_text': 'I built SYNTHETIC: https://synthetic-product.test/',
                'points': 2, 'num_comments': 1,
                'url': 'https://synthetic-product.test/', 'story_id': 123456}

    def body(self, rows):
        return json.dumps({'query': self.query['query'], 'page': 0,
                           'hitsPerPage': 10, 'nbHits': len(rows), 'hits': rows})

    def test_protocol_freezes_exact_scope_and_thirty_day_window(self):
        self.assertEqual([q['query'] for q in self.protocol['queries']],
                         ['AI agent', 'AI tool', 'launched'])
        self.assertEqual(self.protocol['max_returned_hits_total'], 30)
        self.assertEqual(self.protocol['target_returned_hits'], [20, 30])
        cutoff = self.anchor - timedelta(days=30)
        for query in self.protocol['queries']:
            url = urlsplit(query['url'])
            params = parse_qs(url.query)
            self.assertEqual((url.scheme, url.hostname, url.path),
                             ('https', 'hn.algolia.com', '/api/v1/search_by_date'))
            self.assertEqual(params['tags'], ['show_hn'])
            self.assertEqual(params['hitsPerPage'], ['10'])
            self.assertEqual(params['page'], ['0'])
            self.assertEqual(params['numericFilters'], [
                f'created_at_i>={int(cutoff.timestamp())},created_at_i<={int(self.anchor.timestamp())}'])
        self.assertFalse(self.protocol['follow_outbound_links'])
        self.assertEqual(self.protocol['approved_product_urls'], [])

    def test_comment_and_generic_story_cannot_enter_show_hn_population(self):
        for tags in (['comment'], ['story'], ['story', 'show_hn', 'comment'], None):
            row = self.hit()
            row['_tags'] = tags
            with self.subTest(tags=tags), self.assertRaises(DataError):
                parse_response(self.body([row]), self.query, self.protocol)

    def test_outside_date_window_and_timestamp_mismatch_are_rejected(self):
        for created in (self.anchor - timedelta(days=31), self.anchor + timedelta(seconds=1)):
            row = self.hit()
            row.update(created_at=created.isoformat(), created_at_i=int(created.timestamp()))
            with self.subTest(created=created), self.assertRaises(DataError):
                parse_response(self.body([row]), self.query, self.protocol)
        row = self.hit()
        row['created_at'] = self.anchor.isoformat()
        with self.assertRaises(DataError):
            parse_response(self.body([row]), self.query, self.protocol)

    def test_submission_url_without_post_text_is_not_product_url_candidate(self):
        row = self.hit()
        row['story_text'] = None
        item = parse_response(self.body([row]), self.query, self.protocol)[0]
        self.assertEqual(item['source_url_from_response'], row['url'])
        self.assertEqual(item['post_text_urls'], [])
        self.assertFalse(item['product_urls_fetched'])

    def test_provider_signup_words_do_not_verify_payment_or_change_tier(self):
        row = self.hit()
        row['story_text'] += ' Stripe signup pricing checkout.'
        item = parse_response(self.body([row]), self.query, self.protocol)[0]
        self.assertEqual((item['tier'], item['verdict']), ('T3', 'HYPED'))
        self.assertFalse(item['payment_evidence']['present'])
        self.assertFalse(item['buyer_evidence']['present'])
        self.assertFalse(item['founder_identity_verified'])

    def test_entity_encoded_href_retains_real_url_not_abbreviated_display(self):
        text = ('<a href="https:&#x2F;&#x2F;synthetic-product.test&#x2F;really-long-path&#x2F;">'
                'https:&#x2F;&#x2F;synthetic-product.test&#x2F;really-...</a>')
        self.assertEqual(text_urls(text), ['https://synthetic-product.test/really-long-path/'])

    def test_href_legal_trailing_punctuation_is_not_changed(self):
        text = '<a href="https://synthetic-product.test/demo_(v1)">demo</a>'
        self.assertEqual(text_urls(text), ['https://synthetic-product.test/demo_(v1)'])

    def test_plain_url_and_repeated_anchor_are_deduplicated_without_network(self):
        text = ('Try https://synthetic-product.test/demo/ then '
                '<a href="https://synthetic-product.test/demo/">the demo</a>.')
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            self.assertEqual(text_urls(text), ['https://synthetic-product.test/demo/'])

    def test_private_local_credentials_and_nonproduct_sources_are_rejected(self):
        rejected = ('https://127.0.0.1/', 'https://10.1.2.3/', 'https://192.168.0.1/',
                    'https://localhost/', 'https://box.local/', 'https://box.internal/',
                    'https://user:password@synthetic-product.test/',
                    'https://synthetic-product.test:9999/', 'javascript:alert(1)',
                    'https://github.com/synthetic/product', 'https://api.github.com/',
                    'https://news.ycombinator.com/item?id=123',
                    'https://reddit.com/r/synthetic/', 'https://producthunt.com/',
                    'https://synthetic-product.test/\nprivate')
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            for url in rejected:
                with self.subTest(url=url):
                    self.assertFalse(public_product_url(url))
            self.assertTrue(public_product_url('https://synthetic-product.test/demo/'))

    def test_empty_response_is_valid_but_unknown_or_inconsistent_schema_is_not(self):
        self.assertEqual(parse_response(self.body([]), self.query, self.protocol), [])
        for doc in ({}, {'hits': []}, {'query': self.query['query'], 'page': 0,
                     'hitsPerPage': 10, 'nbHits': 2, 'hits': []}):
            with self.subTest(doc=doc), self.assertRaises(DataError):
                parse_response(json.dumps(doc), self.query, self.protocol)

    def test_baseline_audit_rejects_changed_historical_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            snapshot_name = 'artifacts/t7-baseline/snapshot_t0.jsonl'
            snapshot = root / snapshot_name
            snapshot.parent.mkdir(parents=True)
            snapshot.write_text(''.join(json.dumps({'id': i}) + '\n' for i in range(15)), encoding='utf-8')
            digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
            prior = root / 'artifacts/live-evidence-v2/ws3/audit.json'
            prior.parent.mkdir(parents=True)
            prior.write_text(json.dumps({'snapshot': snapshot_name, 'snapshot_sha256': digest,
                              'historical_files_sha256': {snapshot_name: digest}}), encoding='utf-8')
            result = baseline_audit(root)
            self.assertEqual(result['baseline_records'], 15)
            self.assertFalse(result['t7_executed'])
            self.assertEqual(result['new_observations'], 0)
            snapshot.write_bytes(snapshot.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(DataError, 'CRITICAL'):
                baseline_audit(root)


if __name__ == '__main__':
    unittest.main()
