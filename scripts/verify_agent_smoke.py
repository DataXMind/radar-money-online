"""Verify archived Codex smoke outputs and relay measured usage, without model calls."""
import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.codex/hooks'))
import token_guard


def verify(path, relay=False):
    path = (ROOT / path).resolve()
    if not path.is_relative_to((ROOT / 'artifacts/agent-sprint').resolve()) or path.stat().st_size > 10_000_000:
        raise ValueError('only bounded sprint runtime logs are allowed')
    raw = path.read_bytes()
    records = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines()]
    final = None
    session = None
    usage = []
    for index, record in enumerate(records):
        if record.get('type') == 'thread.started':
            session = record['thread_id']
        item = record.get('item', {})
        if item.get('type') == 'agent_message' and item.get('text', '').strip().startswith('{'):
            final = json.loads(item['text'])
        if record.get('type') == 'turn.completed':
            usage.append({'index': index, 'usage': record['usage']})
    if not isinstance(final, dict) or not session or not usage:
        raise ValueError('missing runtime completion evidence')
    expected_names = {p.stem for p in (ROOT / '.codex/agents').glob('*.toml')}
    if len(expected_names) != 13 or set(final['visible_custom_roles']) != expected_names:
        raise ValueError('runtime-visible role list mismatch')
    roles = {'scout_multi_source', 'evidence_auditor', 'vietnam_adapter'}
    results = final['smoke_results']
    if len(results) != 3 or {r['role'] for r in results} != roles:
        raise ValueError('missing smoke role')
    for result in results:
        doc = tomllib.loads((ROOT / '.codex/agents' / (result['role'] + '.toml')).read_text(encoding='utf-8'))
        signature = re.search(r'role_signature "([^"]+)"', doc['developer_instructions']).group(1)
        if (result.get('role_signature') != signature or result.get('status') != 'RESEARCH_DRAFT_ONLY'
                or not result.get('canonical_task_name', '').startswith('/root/')
                or not isinstance(result.get('gaps'), list) or not result['gaps']):
            raise ValueError('smoke output did not demonstrate loaded role instructions')
    warnings = []
    if relay:
        for measured in usage:
            warnings.append(token_guard.handle({'session_id': session, 'turn_id': 'cli-record-' + str(measured['index']),
                              'hook_event_name': 'UsageRelay', 'usage': measured['usage']}))
    return {'status': 'PASS', 'kind': 'runtime_smoke_with_role_markers', 'runtime_parent_sandbox': 'read-only',
            'source': str(path.relative_to(ROOT)).replace('\\', '/'), 'sha256': hashlib.sha256(raw).hexdigest(),
            'visible_custom_roles': sorted(expected_names), 'smoke_results': results,
            'usage': usage, 'token_warnings': warnings,
            'runtime_reported_recoveries': final.get('tool_failures', []),
            'limits': ['CLI stream exposes parent responses and usage; not a complete child tool-call audit.',
                       'Role signatures were requested without giving expected values in the smoke prompt.',
                       'Native hook activation/trust and real compaction were not exercised by this smoke.',
                       'Usage is measured CLI parent usage; child usage is not separately established.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--relay-usage', action='store_true')
    parser.add_argument('--input', default='artifacts/agent-sprint/runtime-smoke-v2.jsonl')
    args = parser.parse_args()
    report = verify(args.input, relay=args.relay_usage)
    path = ROOT / 'artifacts/agent-sprint/smoke_verified.json'
    path.write_bytes((json.dumps(report, ensure_ascii=True, indent=2) + '\n').encode())
    print(json.dumps({'status': report['status'], 'roles': len(report['visible_custom_roles']),
                      'smokes': len(report['smoke_results']), 'token_warnings': report['token_warnings']}))


if __name__ == '__main__':
    main()
