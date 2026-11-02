"""80K/95K warnings using explicit measured CLI usage; no guessed token counts."""
import json
from gold_common import ROOT, atomic_json, cli, locked, now, session_key, state_root, state_file


def handle(event, root=ROOT):
    key = session_key(event)
    state = state_root(root)
    usage = event.get('usage')
    measured = isinstance(usage, dict)
    if measured:
        for field in ('input_tokens', 'output_tokens'):
            if type(usage.get(field)) is not int or usage[field] < 0:
                raise ValueError('invalid usage counters')
        turn = event.get('turn_id')
        if not isinstance(turn, str) or not turn or len(turn) > 256:
            raise ValueError('turn_id required to deduplicate measured usage')
    with locked(state):
        path = state_file(state, 'usage-' + key + '.json')
        data = json.loads(path.read_text()) if path.exists() else {'total': 0, 'turns': []}
        if measured and turn not in data['turns']:
            data['total'] += usage['input_tokens'] + usage['output_tokens']
            data['turns'].append(turn)
            atomic_json(path, data)
        total = data['total'] if data['turns'] else None
        level = '95K' if total is not None and total >= 95_000 else '80K' if total is not None and total >= 80_000 else 'below_threshold' if total is not None else 'usage_unavailable'
        record = {'time': now(), 'session_key': key, 'event': event.get('hook_event_name'),
                  'measured_usage_supplied': measured, 'known_total_tokens': total, 'level': level}
        with state_file(state, 'token-usage.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record) + '\n')
    if level in ('80K', '95K'):
        return {'systemMessage': f'Token warning {level}: measured input+output={total}. Review budget; this is a warning, not a hard cap.'}
    if not measured:
        return {'systemMessage': 'Token usage unavailable in this hook event; no new usage was inferred. Native hook payloads do not guarantee counters.'}
    return {}


if __name__ == '__main__':
    raise SystemExit(cli(handle))
