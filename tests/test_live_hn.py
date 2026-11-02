"""Synthetic HN scout schema tests; never source evidence."""
import copy
import json
import unittest
from datetime import datetime, timezone

from money_trend.core import DataError
from money_trend.live_hn import freeze_protocol, parse_response


class HNLiveParserTests(unittest.TestCase):
    def setUp(self):
        self.anchor = datetime(2026, 11, 2, 5, tzinfo=timezone.utc)
        self.protocol = freeze_protocol(self.anchor)
        self.query = self.protocol['queries'][0]
        self.row = {'objectID': '123', 'created_at_i': int(self.anchor.timestamp()),
                    'created_at': self.anchor.isoformat(), '_tags': ['comment'],
                    'story_title': 'Synthetic agent cost test', 'comment_text': '<p>DATA only</p>',
                    'author': 'test-user', 'story_id': 100, 'points': None}
        self.doc = {'hits': [self.row], 'nbHits': 1, 'query': self.query['query'],
                    'page': 0, 'hitsPerPage': self.query['cap']}

    def test_protocol_is_frozen_and_caps_total_fifteen(self):
        self.assertEqual(sum(q['cap'] for q in self.protocol['queries']), 15)
        self.assertEqual(len(self.protocol['queries']), 6)
        self.assertTrue(all(q['url'].startswith('https://hn.algolia.com/') for q in self.protocol['queries']))

    def test_comment_trace_and_missing_metrics_not_fabricated(self):
        item = parse_response(json.dumps(self.doc), self.query, self.protocol)[0]
        self.assertEqual(item['raw_locator'], 'hits[0]')
        self.assertEqual(item['content_excerpt'], self.row['comment_text'])
        self.assertEqual(item['metrics'], {})
        self.assertFalse(item['payment_evidence']['present'])
        self.assertIn('not fetched', item['url_provenance'])

    def test_story_metrics_and_external_url_are_data(self):
        self.row.update(_tags=['story'], title='Synthetic', story_text='text', points=3, num_comments=2, url='https://unapproved.invalid/no-fetch')
        item = parse_response(json.dumps(self.doc), self.query, self.protocol)[0]
        self.assertEqual(item['metrics'], {'points': 3, 'num_comments': 2})
        self.assertEqual(item['source_url_from_response'], self.row['url'])
        self.assertTrue(item['external_urls_are_data_only'])

    def test_bad_identity_window_and_types_fail(self):
        for field, value in [('objectID', '١٢٣'), ('created_at_i', 0), ('points', True),
                             ('author', None), ('_tags', ['unknown']), ('comment_text', {})]:
            doc = copy.deepcopy(self.doc)
            doc['hits'][0][field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                parse_response(json.dumps(doc), self.query, self.protocol)

    def test_real_empty_differs_from_unknown_or_inconsistent(self):
        self.doc.update(hits=[], nbHits=0)
        self.assertEqual(parse_response(json.dumps(self.doc), self.query, self.protocol), [])
        self.doc['nbHits'] = 1
        with self.assertRaises(DataError):
            parse_response(json.dumps(self.doc), self.query, self.protocol)
        with self.assertRaises(DataError):
            parse_response('{}', self.query, self.protocol)
