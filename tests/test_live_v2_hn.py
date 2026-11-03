"""Offline synthetic HN v2 contracts; no live source or payment evidence."""
import copy
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

from money_trend.core import DataError
from money_trend.live_shared import LiveClient
from money_trend.live_v2_hn import KEYWORDS, freeze_protocol, parse_response, run


class Response(io.BytesIO):
    status = 200
    headers = {'Content-Type': 'application/json'}


class HNV2Tests(unittest.TestCase):
    def setUp(self):
        self.anchor = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
        self.protocol = freeze_protocol(self.anchor)
        self.query = self.protocol['queries'][0]

    def hit(self, ident='100', kind='comment'):
        return {'objectID': ident, 'created_at': '2026-11-01T12:00:00Z',
                'created_at_i': 1793534400, 'author': 'TEST-FOUNDER',
                '_tags': ['comment'] if kind == 'comment' else ['story', 'show_hn'],
                'story_title': 'Synthetic AI product', 'title': 'Show HN: Synthetic AI product',
                'comment_text': 'I built TEST only. Stripe pricing checkout; first customer self-report.',
                'story_text': 'Synthetic report only', 'points': 0, 'num_comments': None,
                'url': 'https://not-approved.invalid/checkout', 'story_id': 90}

    def body(self, rows, query=None):
        query = query or self.query
        return json.dumps({'query': query['query'], 'page': 0, 'hitsPerPage': 2, 'nbHits': len(rows), 'hits': rows})

    def test_frozen_keywords_or_tags_window_and_quotas(self):
        self.assertEqual([q['query'] for q in self.protocol['queries']], KEYWORDS)
        self.assertEqual(self.protocol['max_unique_retained'], 7)
        self.assertEqual(self.protocol['max_returned_hits_total'], 12)
        self.assertIn('tags=%28comment%2Cshow_hn%29', self.query['url'])
        self.assertIn('created_at_i%3E%3D', self.query['url'])
        self.assertIn('created_at_i%3C%3D', self.query['url'])

    def test_comment_signals_remain_unverified_and_external_url_data(self):
        result = parse_response(self.body([self.hit()]), self.query, self.protocol)[0]
        self.assertTrue(result['lexical_signals']['provider'])
        self.assertTrue(result['lexical_signals']['checkout'])
        self.assertTrue(result['lexical_signals']['customer_allegation'])
        self.assertFalse(result['payment_infrastructure_verified'])
        self.assertFalse(result['payment_evidence']['present'])
        self.assertEqual(result['source_url_from_response'], 'https://not-approved.invalid/checkout')
        self.assertEqual(result['raw_locator'], 'hits[0]')
        self.assertEqual(result['metrics']['points'], 0)

    def test_show_hn_allowed_generic_story_and_wrong_dates_rejected(self):
        parse_response(self.body([self.hit(kind='story')]), self.query, self.protocol)
        row = self.hit(kind='story'); row['_tags'] = ['story']
        with self.assertRaises(DataError):
            parse_response(self.body([row]), self.query, self.protocol)
        for field, value in [('created_at_i', 1), ('created_at', '2026-11-01T12:00:00')]:
            row = self.hit(); row[field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                parse_response(self.body([row]), self.query, self.protocol)

    def test_genuine_empty_differs_unknown_or_inconsistent(self):
        self.assertEqual(parse_response(self.body([]), self.query, self.protocol), [])
        for doc in ({}, {'hits': []}, {'query': self.query['query'], 'page': 0, 'hitsPerPage': 2, 'nbHits': 2, 'hits': []}):
            with self.subTest(doc=doc), self.assertRaises(DataError):
                parse_response(json.dumps(doc), self.query, self.protocol)

    def test_one_batch_deduplicates_caps_seven_saves_raw_and_refuses_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            responses = []
            for i, query in enumerate(self.protocol['queries']):
                rows = [self.hit(str(i * 2 + j + 100)) for j in range(2)]
                responses.append(Response(self.body(rows, query).encode()))
            clients = []
            def factory(path, **kwargs):
                self.assertEqual(kwargs['allowed_hosts'], ('hn.algolia.com',))
                client = LiveClient(path, sleeper=lambda _: None, **kwargs)
                client.opener.open = Mock(side_effect=responses)
                clients.append(client)
                return client
            result = run(root, factory, self.anchor)
            self.assertEqual(result['retained_items'], 7)
            self.assertEqual(result['returned_hits'], 12)
            self.assertEqual(result['request_attempts'], 6)
            self.assertEqual(result['opportunities'], [])
            self.assertEqual(clients[0].opener.open.call_count, 6)
            records = [json.loads(line) for line in (root / 'artifacts/live-evidence-v2/hn_evidence.jsonl').read_text().splitlines()]
            self.assertEqual(len(records), 7)
            self.assertTrue(all((root / r['raw_response_path']).is_file() for r in records))
            with self.assertRaises(FileExistsError):
                run(root, factory, self.anchor)
            self.assertEqual(clients[0].opener.open.call_count, 6)


if __name__ == '__main__':
    unittest.main()
