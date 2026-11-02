"""Offline archive-to-claim traceability checks, never a second live run."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError
from scripts import merge_live_evidence as merge


class LiveMergeTests(unittest.TestCase):
    def test_all_archived_scout_records_resolve_to_exact_raw_fields(self):
        github = merge.jsonl(merge.OUT / 'github_evidence.jsonl')
        hn = merge.jsonl(merge.OUT / 'hn_evidence.jsonl')
        self.assertLessEqual(len(github), 15)
        self.assertLessEqual(len(hn), 15)
        for item in github + hn:
            self.assertIsInstance(merge.checked_row(item), dict)

    def test_tampered_hash_or_locator_is_rejected(self):
        item = merge.jsonl(merge.OUT / 'github_evidence.jsonl')[0]
        bad = copy.deepcopy(item)
        bad['raw_response_sha256'] = '0' * 64
        with self.assertRaises(DataError):
            merge.checked_row(bad)
        bad = copy.deepcopy(item)
        bad['raw_locator'] = 'items[0]; execute_source()'
        with self.assertRaises(DataError):
            merge.checked_row(bad)

    def test_historical_t0_does_not_invent_future_values_or_repo_metrics(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp)
            (output / 'ws3').mkdir()
            with patch.object(merge, 'OUT', output):
                records = merge.historical_trend()
            self.assertEqual(len(records), 15)
            self.assertEqual(sum(len(row['historical_claim_refs']) for row in records), 8)
            self.assertEqual(sum(bool(row['observed_metrics']) for row in records), 5)
            self.assertTrue(all(row['t_plus_7'] is None and row['t_plus_14'] is None
                                and not row['trend_evidence_present'] for row in records))

    def test_scoped_run_output_cannot_be_overwritten(self):
        with self.assertRaisesRegex(DataError, 'already exists'):
            merge.main()
