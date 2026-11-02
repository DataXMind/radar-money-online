"""Unregister only unchanged Gold handlers; optionally archive owned agents. No recursive delete."""
import argparse
import hashlib
import json
from gold_common import ROOT, atomic_json, backup, parse_json


def uninstall(root=ROOT, remove_agents=False):
    registry = root / '.codex/gold-registration.json'
    registration = parse_json(registry.read_text(encoding='utf-8'))
    target = root / '.codex/hooks.json'
    changed = False
    if target.exists():
        config = parse_json(target.read_text(encoding='utf-8'))
        for event, owned_groups in registration['hooks'].items():
            groups = config.get('hooks', {}).get(event, [])
            filtered = [group for group in groups if group not in owned_groups]
            if filtered != groups:
                config['hooks'][event] = filtered
                changed = True
        if changed:
            backup(target)
            atomic_json(target, config)
    removed = []
    if remove_agents:
        # Refuse the entire removal phase before changing any modified agent.
        candidates = []
        for name, expected in registration['agents_sha256'].items():
            path = (root / '.codex/agents' / name).resolve()
            if not path.is_relative_to((root / '.codex/agents').resolve()):
                raise ValueError('unsafe agent registry path')
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError('agent changed; manual review required: ' + name)
                candidates.append(path)
        for path in candidates:
            backup(path)
            path.unlink()
            removed.append(path.name)
    return {'hooks_changed': changed, 'agents_archived': removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remove-agents', action='store_true')
    args = parser.parse_args()
    print(json.dumps(uninstall(remove_agents=args.remove_agents)))


if __name__ == '__main__':
    main()
