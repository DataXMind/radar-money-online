"""Idempotently merge project hooks; back up changed files before writing."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gold_install_common', ROOT / '.codex/hooks/gold_common.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def definitions():
    # Hook commands are trusted config, never built from event input.
    # Resolve from the git root, so starting in a repo subdirectory works.
    def group(script, matcher=None, context=False):
        handler = {'type': 'command', 'command': f'python3 "$(git rev-parse --show-toplevel)/.codex/hooks/{script}"',
                   'commandWindows': f'powershell.exe -NoProfile -Command "& python (Join-Path (git rev-parse --show-toplevel) \'.codex/hooks/{script}\')"',
                   'timeout': 5}
        result = {'hooks': [handler]}
        if matcher is not None:
            result['matcher'] = matcher
        if context:
            handler['additionalContextLimit'] = 1500
        return result
    return {
        'PreToolUse': [group('token_guard.py')],
        'PreCompact': [group('save_context.py', 'manual|auto')],
        'PostCompact': [group('restore_context.py', 'manual|auto')],
        'SessionStart': [group('restore_context.py', '^compact$', context=True)],
        'Stop': [group('validate_output.py')],
        'SubagentStop': [group('validate_output.py')],
    }


def install(root=ROOT):
    target = root / '.codex/hooks.json'
    registry = root / '.codex/gold-registration.json'
    desired = definitions()
    config = common.parse_json(target.read_text(encoding='utf-8')) if target.exists() else {'hooks': {}}
    if not isinstance(config, dict) or not isinstance(config.get('hooks'), dict):
        raise ValueError('existing hooks config must be an object')
    old = common.parse_json(registry.read_text()) if registry.exists() else {'hooks': {}}
    before = json.dumps(config, sort_keys=True)
    new_owned = {}
    for event in set(desired) | set(old['hooks']):
        groups = config['hooks'].get(event, [])
        if not isinstance(groups, list):
            raise ValueError('hook event must be a list')
        owned = old['hooks'].get(event, [])
        groups = [group for group in groups if group not in owned]
        new_owned[event] = []
        for group in desired.get(event, []):
            if group not in groups:
                groups.append(group)
                new_owned[event].append(group)
        config['hooks'][event] = groups
    changed = before != json.dumps(config, sort_keys=True)
    if changed:
        if target.exists():
            common.backup(target)
        common.atomic_json(target, config)
    registration = {'version': 1, 'hooks': new_owned,
                    'agents_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted((root / '.codex/agents').glob('*.toml'))}}
    if not registry.exists() or common.parse_json(registry.read_text()) != registration:
        if registry.exists():
            common.backup(registry)
        common.atomic_json(registry, registration)
    return changed


if __name__ == '__main__':
    print(json.dumps({'hooks_changed': install(), 'trust': 'Review exact definitions with /hooks; trust is not bypassed.'}))
