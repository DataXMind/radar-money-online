"""Offline-only production preparation tests; all outputs/approvals are temporary."""
import copy
import json
import shutil
import socket
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError, strict_json, write_json
from scripts import run_production as production

REPO = Path(__file__).resolve().parents[1]


class ProductionPreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('config/approvals', 'docs', 'artifacts/offline-production-prep'):
            (self.root / folder).mkdir(parents=True)
        for name in ('config/production_v1.json', 'docs/evidence_criteria.md', 'dashboard.md'):
            shutil.copyfile(REPO / name, self.root / name)
        shutil.copytree(REPO / 'artifacts/mvp-v1', self.root / 'artifacts/mvp-v1')
        self.addCleanup(patch.stopall)
        patch.object(production, 'ROOT', self.root).start()
        self.now = datetime(2026, 11, 2, 3, 5, tzinfo=timezone.utc)
        clock = patch.object(production, 'datetime', wraps=datetime).start()
        clock.now.return_value = self.now
        self.report_path = self.root / 'artifacts/offline-production-prep/offline_tests.json'
        log = self.report_path.with_name('offline_tests.txt')
        log.write_bytes(b'Synthetic report persistence fixture, not a real test result\n')
        write_json(self.report_path, {'status': 'PASS', 'tests_run': 1, 'failures': 0, 'errors': 0,
                                    'source_sha256': {}, 'log_sha256': production.sha(log)})
        self.config_path = self.root / 'config/production_v1.json'
        self.config = strict_json(self.config_path.read_text())
        report = strict_json(self.report_path.read_text())
        report['production_bundle_sha256'] = {
            k: v for k, v in production.approval_bindings(self.config_path, self.config).items()
            if k != 'test_report_sha256'}
        write_json(self.report_path, report)
        self.approval_path = self.root / 'config/approvals/test-only.json'
        self.approval = {'approved': True, 'action': 'RUN_OFFLINE_DRAFT', 'reviewer': 'TEST ONLY',
                         'approved_at': self.now.isoformat(), 'run_id': 'test-only',
                         'output_root': self.config['output_root'],
                         **production.approval_bindings(self.config_path, self.config)}
        write_json(self.approval_path, self.approval)

    def execute(self):
        return production.execute('config/production_v1.json', 'config/approvals/test-only.json', 'test-only')

    def test_offline_archive_report_keeps_draft_and_empty_csv(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no HTTP')) as http:
            out = self.execute()
        http.assert_not_called()
        manifest = strict_json((out / 'run_manifest.json').read_text())
        ledger = strict_json((out / 'evidence_ledger.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['run_kind'], 'offline_archive_replay')
        self.assertFalse(manifest['network_enabled'])
        self.assertEqual(manifest['raw_count'], 15)
        self.assertEqual(manifest['claim_count'], 8)
        self.assertEqual(manifest['status'], 'RESEARCH_DRAFT_ONLY')
        self.assertEqual(ledger['opportunities'], [])
        self.assertEqual(len((out / 'opportunities.csv').read_text().splitlines()), 1)
        self.assertIn('NO_VERIFIED_BUYER', ' '.join(manifest['kill_reasons']))
        self.assertIn('MISSING_TREND', ' '.join(manifest['kill_reasons']))
        self.assertIn('offline replay', ' '.join((out / 'dashboard.md').read_text().split()))
        for name, digest in manifest['artifacts_sha256'].items():
            self.assertEqual(production.sha(out / name), digest)

    def test_missing_approval_never_creates_output(self):
        self.approval_path.unlink()
        with self.assertRaises(OSError):
            self.execute()
        self.assertFalse((self.root / 'artifacts/production-v1').exists())

    def test_wrong_expired_or_unapproved_authorization_is_blocked(self):
        for field, value in [('approved', False), ('run_id', 'other'), ('config_sha256', 'wrong'),
                             ('approved_at', '2026-10-01T00:00:00Z'),
                             ('approved_at', '2026-11-03T00:00:00Z')]:
            with self.subTest(field=field, value=value):
                approval = {**self.approval, field: value}
                write_json(self.approval_path, approval)
                with self.assertRaises(DataError):
                    self.execute()
        self.assertFalse((self.root / 'artifacts/production-v1').exists())

    def test_network_mode_or_weakened_policy_is_rejected(self):
        for field, value in [('network_enabled', True), ('option', 'A'), ('window_days', 14),
                             ('execution_mode', 'AUTO'), ('required_evidence', []),
                             ('limits', {'raw_items': 16, 'claims': 8, 'opportunities': 5})]:
            with self.subTest(field=field), self.assertRaises(DataError):
                production.validate_config({**self.config, field: value})

    def test_changed_criteria_or_test_log_blocks_preflight(self):
        criteria = self.root / 'docs/evidence_criteria.md'
        original = criteria.read_bytes()
        criteria.write_bytes(original + b'changed')
        with self.assertRaisesRegex(DataError, 'criteria changed'):
            self.execute()
        criteria.write_bytes(original)
        self.report_path.with_name('offline_tests.txt').write_bytes(b'tampered')
        with self.assertRaisesRegex(DataError, 'test log hash'):
            self.execute()

    def test_test_report_must_match_prepared_script_and_config(self):
        report = strict_json(self.report_path.read_text())
        report['production_bundle_sha256']['script_sha256'] = 'stale-script'
        write_json(self.report_path, report)
        with self.assertRaisesRegex(DataError, 'current passing offline test report'):
            self.execute()

    def test_stale_cache_is_gap_never_network_refresh(self):
        with patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('no HTTP')) as http:
            items, errors = production.read_archive(self.config, datetime(2026, 11, 20, tzinfo=timezone.utc), lambda *a, **kw: None)
        self.assertEqual(items, [])
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(e.startswith('STALE_OR_FUTURE_ARCHIVE') for e in errors))
        http.assert_not_called()

    def test_corrupt_cache_produces_draft_error_artifacts(self):
        raw = next((self.root / 'artifacts/mvp-v1/requests').glob('*.body'))
        raw.write_bytes(b'corrupted')
        out = self.execute()
        manifest = strict_json((out / 'run_manifest.json').read_text())
        self.assertEqual(manifest['opportunity_count'], 0)
        self.assertTrue(any('ARCHIVE_INGRESS_ERROR' in r for r in manifest['kill_reasons']))

    def test_source_cannot_trigger_network_in_offline_execution(self):
        with patch.object(production, 'read_archive', side_effect=lambda *a: socket.socket()):
            out = self.execute()
        manifest = strict_json((out / 'run_manifest.json').read_text())
        self.assertTrue(any('network disabled' in r for r in manifest['kill_reasons']))

    def test_run_id_and_config_paths_cannot_escape(self):
        for run_id in ('../escape', '', 'a/b'):
            with self.subTest(run_id=run_id), self.assertRaises(DataError):
                production.preflight('config/production_v1.json', 'config/approvals/test-only.json', run_id, self.now)
        with self.assertRaises(DataError):
            production.confined('../escape', self.root / 'config')

    def test_existing_run_cannot_be_overwritten(self):
        self.execute()
        with self.assertRaises(FileExistsError):
            self.execute()

    def test_boolean_evidence_summaries_never_bypass_option_b(self):
        candidate = {'buyer_evidence': {'present': True, 'proof_type': 'receipt', 'url': 'TEST ONLY'},
                     'payment_evidence': {'present': True, 'proof_type': 'receipt', 'url': 'TEST ONLY'},
                     'trend_evidence': {'present': True, 'cohort': 'TEST ONLY', 't0': 'TEST ONLY',
                                        't_plus': 'TEST ONLY', 'metric': 'TEST ONLY'}}
        self.assertEqual(len(production.evidence_gaps(candidate)), 1)
        for name in production.REQUIRED:
            incomplete = copy.deepcopy(candidate)
            incomplete[name]['present'] = False
            self.assertIn('MISSING_' + name.upper(), production.evidence_gaps(incomplete))
