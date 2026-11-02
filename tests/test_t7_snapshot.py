"""Offline baseline checks; temporary outputs, original public archive inputs."""
import hashlib
import json
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError
from scripts import prepare_t7_snapshot as prep

ROOT = Path(__file__).resolve().parents[1]


class T7PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / 'artifacts/mvp-v1', self.root / 'artifacts/mvp-v1')

    def test_frozen_fifteen_records_exact_ids_original_counters_and_no_network(self):
        with (patch.object(socket, 'socket', side_effect=AssertionError('no network')),
              patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no HTTP')) as http):
            out = prep.prepare(self.root)
        http.assert_not_called()
        rows = [json.loads(line) for line in (out / 'snapshot_t0.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 15)
        self.assertEqual([(r['source'], r['stable_id']) for r in rows], prep.COHORT)
        self.assertEqual(rows[10]['counters']['points']['value'], 2346)
        self.assertEqual(rows[10]['counters']['num_comments']['value'], 951)
        self.assertEqual(rows[10]['counters']['num_comments']['raw_locator'], 'hits[0].num_comments')
        self.assertEqual(rows[0]['counters']['followers']['value'], 27683)
        self.assertEqual(rows[0]['counters']['help_wanted_issues_count']['value'], 0)
        self.assertIsNone(rows[0]['counters']['stargazers_count']['value'])
        self.assertIsNone(rows[0]['counters']['total_issues']['value'])
        self.assertEqual(rows[0]['scheduled_t7'], '2026-11-09T03:01:40.308906+00:00')
        self.assertTrue(all(r['delta'] is None and not r['trend_evidence_present'] for r in rows))
        self.assertTrue(all(r['followup_observed_at'] is None for r in rows))
        manifest = json.loads((out / 'run_manifest.json').read_text())
        self.assertEqual(manifest['network_requests'], 0)
        self.assertFalse(manifest['t7_executed'])
        for name, digest in manifest['artifacts_sha256'].items():
            self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest)

    def test_real_zero_and_missing_null_stay_distinct(self):
        self.assertEqual(prep.counter(0, 'raw.field')['value'], 0)
        self.assertIsNone(prep.counter(None, None, 'missing')['value'])
        for value in (False, -1, '0'):
            with self.subTest(value=value), self.assertRaises(DataError):
                prep.counter(value, 'raw.field')

    def test_tampered_raw_or_ledger_is_rejected_before_output(self):
        for name in ('requests/5e98cd643ddf_001_github_1.body', 'evidence_ledger.json'):
            path = self.root / 'artifacts/mvp-v1' / name
            original = path.read_bytes()
            path.write_bytes(original + b'tampered')
            with self.subTest(name=name), self.assertRaisesRegex(DataError, 'artifact hash mismatch'):
                prep.prepare(self.root)
            self.assertFalse((self.root / 'artifacts/t7-baseline').exists())
            path.write_bytes(original)

    def test_manifest_identity_pin_rejects_rewritten_cohort(self):
        path = self.root / 'artifacts/mvp-v1/run_manifest.json'
        manifest = json.loads(path.read_text())
        manifest['raw_count'] = 16
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(DataError, 'manifest pin mismatch'):
            prep.prepare(self.root)
        self.assertFalse((self.root / 'artifacts/t7-baseline').exists())

    def test_existing_baseline_and_historical_bytes_never_overwritten(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes()
                  for p in (self.root / 'artifacts/mvp-v1').rglob('*') if p.is_file()}
        out = prep.prepare(self.root)
        snapshot = (out / 'snapshot_t0.jsonl').read_bytes()
        with self.assertRaises(FileExistsError):
            prep.prepare(self.root)
        self.assertEqual(snapshot, (out / 'snapshot_t0.jsonl').read_bytes())
        for name, value in before.items():
            self.assertEqual((self.root / name).read_bytes(), value)

