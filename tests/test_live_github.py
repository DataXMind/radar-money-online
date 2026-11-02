"""Synthetic offline GitHub issue-search schema tests, not live evidence."""
import json
import unittest

from money_trend.core import DataError
from money_trend.live_github import parse_issues


def issue():
    return {'id': 1, 'number': 1, 'comments': 0, 'html_url': 'https://github.com/example/demo/issues/1',
            'title': 'Synthetic cost report', 'body': 'TEST ONLY', 'user': {'login': 'example'},
            'created_at': '2026-10-01T00:00:00Z', 'updated_at': '2026-11-01T00:00:00Z'}


def doc(rows):
    return {'total_count': len(rows), 'incomplete_results': False, 'items': rows}


class LiveGithubTests(unittest.TestCase):
    def test_real_empty_distinguished_from_unknown(self):
        self.assertEqual(parse_issues(json.dumps(doc([])), 3)[1], [])
        for value in ({}, {'message': 'rate limit'}, {'total_count': 1, 'incomplete_results': False, 'items': []}):
            with self.subTest(value=value), self.assertRaises(DataError):
                parse_issues(json.dumps(value), 3)

    def test_valid_identity_provenance_fields(self):
        value = issue()
        parsed = parse_issues(json.dumps(doc([value])), 3)[1]
        self.assertEqual(parsed[0]['id'], 1)

    def test_incomplete_and_invalid_fields_rejected(self):
        incomplete = doc([issue()]); incomplete['incomplete_results'] = True
        with self.assertRaises(DataError): parse_issues(json.dumps(incomplete), 3)
        for field, value in [('id', True), ('comments', -1), ('html_url', 'https://evil.example/x'),
                             ('body', {}), ('updated_at', None)]:
            row = issue(); row[field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                parse_issues(json.dumps(doc([row])), 3)

    def test_pull_request_and_over_quota_rejected(self):
        row = issue(); row['pull_request'] = {}
        with self.assertRaises(DataError): parse_issues(json.dumps(doc([row])), 3)
        with self.assertRaises(DataError): parse_issues(json.dumps(doc([issue(), issue()])), 1)
