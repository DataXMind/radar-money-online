"""PreCompact: snapshot only reviewed project notes, never a transcript."""
import hashlib
from gold_common import ROOT, atomic_json, cli, locked, now, session_key, state_root


def handle(event, root=ROOT):
    key = session_key(event)
    state = state_root(root)
    notes = root / '.codex/context.md'
    if notes.is_symlink() or not notes.resolve().is_relative_to(root.resolve()) or notes.stat().st_size > 8192:
        raise ValueError('invalid reviewed notes path/size')
    raw = notes.read_bytes()
    raw.decode('utf-8')
    with locked(state):
        atomic_json(state / ('context-' + key + '.json'), {
            'saved_at': now(), 'notes': raw.decode('utf-8'),
            'sha256': hashlib.sha256(raw).hexdigest(), 'source': '.codex/context.md'})
    return {'systemMessage': 'Saved reviewed project notes before compaction; transcripts were not read.'}


if __name__ == '__main__':
    raise SystemExit(cli(handle))
