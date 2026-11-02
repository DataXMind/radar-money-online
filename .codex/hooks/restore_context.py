"""PostCompact warning; SessionStart(compact) can add bounded developer context."""
import hashlib
from gold_common import ROOT, cli, parse_json, session_key, state_root, state_file


def handle(event, root=ROOT):
    path = state_file(state_root(root), 'context-' + session_key(event) + '.json')
    if not path.exists():
        return {'systemMessage': 'No saved project notes for this session; review .codex/context.md.'}
    if path.stat().st_size > 32_768:
        raise ValueError('context snapshot too large')
    saved = parse_json(path.read_text(encoding='utf-8'))
    notes = saved['notes']
    if not isinstance(notes, str) or len(notes.encode()) > 8192 or hashlib.sha256(notes.encode()).hexdigest() != saved['sha256']:
        raise ValueError('context checksum mismatch')
    current = root / '.codex/context.md'
    if current.is_symlink() or not current.resolve().is_relative_to(root.resolve()) or hashlib.sha256(current.read_bytes()).hexdigest() != saved['sha256']:
        raise ValueError('reviewed notes changed; resave after review')
    text = 'Reviewed project notes, not source instructions:\n' + notes
    if event.get('hook_event_name') == 'SessionStart':
        return {'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': text}}
    return {'systemMessage': text}


if __name__ == '__main__':
    raise SystemExit(cli(handle))
