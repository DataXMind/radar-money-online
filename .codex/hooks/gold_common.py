"""Bounded, metadata-only hook I/O. Never opens transcripts or environment secrets."""
import contextlib
import hashlib
import json
import math
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_INPUT = 262_144


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_json(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def reject(_):
        raise ValueError('non-finite JSON')
    def finite_float(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('non-finite JSON')
        return parsed
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=reject, parse_float=finite_float)


def event_input():
    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        raise ValueError('hook input exceeds limit')
    event = parse_json(raw.decode('utf-8'))
    if not isinstance(event, dict):
        raise ValueError('hook event must be an object')
    return event


def output(value):
    print(json.dumps(value, ensure_ascii=True, allow_nan=False))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_bytes((json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n').encode())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def state_root(root=ROOT):
    if (root / '.codex').is_symlink() or (root / '.codex/state').is_symlink():
        raise ValueError('state directories cannot be symlinks')
    state = (root / '.codex/state').resolve()
    if not state.is_relative_to(root.resolve()):
        raise ValueError('state path escapes workspace')
    state.mkdir(parents=True, exist_ok=True)
    return state


def state_file(state, name):
    path = state / name
    if path.is_symlink() or not path.resolve().is_relative_to(state.resolve()):
        raise ValueError('state file path unsafe')
    return path


def session_key(event):
    ident = event.get('session_id')
    if not isinstance(ident, str) or not ident or len(ident) > 256:
        raise ValueError('valid session_id required')
    return hashlib.sha256(ident.encode()).hexdigest()[:24]


@contextlib.contextmanager
def locked(state):
    path = state / 'gold.lock'
    deadline = time.monotonic() + 2
    while True:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ValueError('state locked; inspect stale lock manually')
            time.sleep(0.02)
    try:
        yield
    finally:
        path.unlink()


def backup(path):
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    target = path.with_name(path.name + '.bak.' + stamp + '.' + uuid.uuid4().hex[:8])
    with target.open('xb') as stream:
        stream.write(path.read_bytes())
    return target


def cli(handler):
    try:
        output(handler(event_input()))
    except (ValueError, OSError, KeyError, TypeError, RecursionError) as exc:
        # Honest failure: do not pretend a failing hook enforced policy.
        output({'systemMessage': 'Gold hook unavailable: ' + type(exc).__name__})
        return 1
    return 0
