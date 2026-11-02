"""Offline tests: synthetic hook events, temporary state only; no Codex/model calls."""
import copy
import hashlib
import json
import sys
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / '.codex/hooks'
sys.path.insert(0, str(HOOKS))
import token_guard
import save_context
import restore_context
import validate_output
import uninstall
import gold_common
from scripts import install_gold_pattern as installer

NAMES = set('scout_multi_source scout_github scout_vn normalizer claim_extractor mechanism_analyst evidence_auditor vietnam_adapter synthesizer action_planner fact_checker final_editor repo_discovery'.split())


class AgentConfigTests(unittest.TestCase):
    def test_exactly_thirteen_parse_with_only_verified_fields(self):
        paths = list((ROOT / '.codex/agents').glob('*.toml'))
        self.assertEqual({p.stem for p in paths}, NAMES)
        for path in paths:
            doc = tomllib.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(set(doc), {'name', 'description', 'developer_instructions', 'model', 'model_reasoning_effort'})
            self.assertEqual(doc['name'], path.stem)
            self.assertEqual(doc['model'], 'gpt-6.1-sol')
            self.assertIn(doc['model_reasoning_effort'], ('medium', 'high'))
            if path.stem in ('fact_checker', 'final_editor'):
                self.assertIn('Do not edit, create, or delete any files. Read-only analysis only.', doc['developer_instructions'])


class TempHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / '.codex').mkdir()

    def test_token_thresholds_and_duplicate_turns(self):
        event = {'session_id': 'test-only', 'turn_id': 'turn-1', 'hook_event_name': 'UsageRelay',
                 'usage': {'input_tokens': 79_000, 'output_tokens': 1000}}
        self.assertIn('80K', token_guard.handle(event, self.root)['systemMessage'])
        token_guard.handle(event, self.root)
        event['turn_id'] = 'turn-2'
        event['usage'] = {'input_tokens': 14_000, 'output_tokens': 1000}
        self.assertIn('95K', token_guard.handle(event, self.root)['systemMessage'])
        records = [json.loads(line) for line in (self.root / '.codex/state/token-usage.jsonl').read_text().splitlines()]
        self.assertEqual([r['known_total_tokens'] for r in records], [80_000, 80_000, 95_000])

    def test_strict_json_and_unsafe_state_are_rejected(self):
        for raw in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                gold_common.parse_json(raw)
        with patch.object(Path, 'is_symlink', return_value=True), self.assertRaises(ValueError):
            token_guard.handle({'session_id': 'test'}, self.root)

    def test_validator_command_stdin_stdout_contract(self):
        message = {'status': 'RESEARCH_DRAFT_ONLY', 'raw_items': [], 'claims': [],
                   'opportunities': [], 'gaps': ['No evidence']}
        event = {'hook_event_name': 'Stop', 'last_assistant_message': json.dumps(message)}
        result = subprocess.run([sys.executable, str(HOOKS / 'validate_output.py')], input=json.dumps(event),
                                text=True, capture_output=True, cwd=self.root, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PASS', json.loads(result.stdout)['systemMessage'])

    def test_missing_usage_is_unknown_not_zero(self):
        output = token_guard.handle({'session_id': 'new-session', 'hook_event_name': 'PreToolUse'}, self.root)
        self.assertIn('unavailable', output['systemMessage'])
        record = json.loads((self.root / '.codex/state/token-usage.jsonl').read_text())
        self.assertIsNone(record['known_total_tokens'])

    def test_invalid_usage_rejected_and_session_path_not_used(self):
        for value in (True, -1, '80000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                token_guard.handle({'session_id': '../../escape', 'turn_id': 't', 'usage': {'input_tokens': value, 'output_tokens': 0}}, self.root)
        token_guard.handle({'session_id': '../../escape'}, self.root)
        self.assertTrue((self.root / '.codex/state/token-usage.jsonl').exists())

    def test_compaction_round_trip_without_reading_transcript(self):
        notes = self.root / '.codex/context.md'
        notes.write_bytes(b'Keep draft. No production.\n')
        event = {'session_id': 'test-only', 'hook_event_name': 'PreCompact',
                 'transcript_path': 'DO_NOT_OPEN_THIS_FILE'}
        save_context.handle(event, self.root)
        event['hook_event_name'] = 'PostCompact'
        self.assertIn('Keep draft.', restore_context.handle(event, self.root)['systemMessage'])
        event['hook_event_name'] = 'SessionStart'
        restored = restore_context.handle(event, self.root)
        self.assertIn('Keep draft.', restored['hookSpecificOutput']['additionalContext'])
        notes.write_bytes(b'changed notes')
        with self.assertRaises(ValueError):
            restore_context.handle(event, self.root)

    def test_context_tampering_is_rejected(self):
        (self.root / '.codex/context.md').write_bytes(b'reviewed notes')
        event = {'session_id': 'test-only'}
        save_context.handle(event, self.root)
        snapshot = next((self.root / '.codex/state').glob('context-*.json'))
        doc = json.loads(snapshot.read_text())
        doc['notes'] = 'tampered'
        snapshot.write_text(json.dumps(doc))
        with self.assertRaises(ValueError):
            restore_context.handle(event, self.root)

    def output_fixture(self):
        raw = self.root / 'artifacts/raw.body'
        raw.parent.mkdir()
        raw.write_bytes(b'SYNTHETIC TEST DATA ONLY')
        return {'status': 'RESEARCH_DRAFT_ONLY', 'raw_items': [
                    {'evidence_id': 'E1', 'url': 'https://github.com/example/demo',
                     'response_body': 'artifacts/raw.body', 'response_sha256': hashlib.sha256(raw.read_bytes()).hexdigest()}],
                'claims': [{'claim_id': 'C1', 'statement': 'Synthetic test observation', 'evidence_ids': ['E1']}],
                'opportunities': [], 'gaps': ['No verified buyer/payment/trend proof']}

    def test_valid_output_and_raw_hash_checks(self):
        doc = self.output_fixture()
        self.assertTrue(validate_output.validate(doc, self.root))
        (self.root / 'artifacts/raw.body').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            validate_output.validate(doc, self.root)

    def test_validator_rejects_bypasses(self):
        doc = self.output_fixture()
        cases = []
        for field, value in [('status', 'PRODUCTION_READY'), ('opportunities', [{'title': 'invented'}]),
                             ('gaps', []), ('raw_items', doc['raw_items'] * 16), ('claims', doc['claims'] * 9)]:
            cases.append({**doc, field: value})
        missing_ref = copy.deepcopy(doc)
        missing_ref['claims'][0]['evidence_ids'] = ['missing']
        cases.append(missing_ref)
        emerging = copy.deepcopy(doc)
        emerging['claims'][0]['verdict'] = 'EMERGING'
        cases.append(emerging)
        escaping = copy.deepcopy(doc)
        escaping['raw_items'][0]['response_body'] = '../outside'
        cases.append(escaping)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_output.validate(case, self.root)

    def test_stop_validator_is_scoped_and_cannot_loop_forever(self):
        ordinary = validate_output.handle({'last_assistant_message': 'Code committed.'}, self.root)
        self.assertNotIn('decision', ordinary)
        bad = {'last_assistant_message': '{"status":"EMERGING"}'}
        self.assertEqual(validate_output.handle(bad, self.root)['decision'], 'block')
        bad['stop_hook_active'] = True
        self.assertFalse(validate_output.handle(bad, self.root)['continue'])
        valid = {'status': 'RESEARCH_DRAFT_ONLY', 'raw_items': [], 'claims': [], 'opportunities': [], 'gaps': ['No evidence']}
        self.assertIn('PASS', validate_output.handle({'last_assistant_message': json.dumps(valid)}, self.root)['systemMessage'])

    def test_install_idempotent_backup_and_rollback_preserve_other_hooks(self):
        target = self.root / '.codex/hooks.json'
        user_group = {'hooks': [{'type': 'command', 'command': 'USER_HOOK_DO_NOT_RUN'}]}
        original = {'hooks': {'Stop': [user_group]}}
        target.write_text(json.dumps(original))
        self.assertTrue(installer.install(self.root))
        first = target.read_bytes()
        backups = list((self.root / '.codex').glob('*.bak.*'))
        self.assertTrue(backups)
        self.assertFalse(installer.install(self.root))
        self.assertEqual(first, target.read_bytes())
        self.assertEqual(backups, list((self.root / '.codex').glob('*.bak.*')))
        result = uninstall.uninstall(self.root)
        self.assertTrue(result['hooks_changed'])
        self.assertIn(user_group, json.loads(target.read_text())['hooks']['Stop'])
        self.assertFalse(uninstall.uninstall(self.root)['hooks_changed'])

    def test_preexisting_identical_handler_is_not_owned_or_removed(self):
        desired = installer.definitions()['Stop'][0]
        target = self.root / '.codex/hooks.json'
        target.write_text(json.dumps({'hooks': {'Stop': [desired]}}))
        installer.install(self.root)
        uninstall.uninstall(self.root)
        self.assertIn(desired, json.loads(target.read_text())['hooks']['Stop'])

    def test_optional_agent_removal_archives_and_refuses_modified_files(self):
        folder = self.root / '.codex/agents'
        folder.mkdir()
        agent = folder / 'test.toml'
        agent.write_bytes(b'name="test"')
        installer.install(self.root)
        agent.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            uninstall.uninstall(self.root, remove_agents=True)
        agent.write_bytes(b'name="test"')
        result = uninstall.uninstall(self.root, remove_agents=True)
        self.assertEqual(result['agents_archived'], ['test.toml'])
        self.assertTrue(list(folder.glob('test.toml.bak.*')))
