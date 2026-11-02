"""Offline runner: block all sockets; write a verifiable current-source report."""
import hashlib
import argparse
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from .core import utc, write_json


def write_report(out, log, result, root):
    """Persist canonical LF bytes and hash the file actually written."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / 'offline_tests.txt'
    log_path.write_bytes(log.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8'))
    hashes = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('money_trend', 'tests') for p in sorted((root / folder).rglob('*.py'))}
    report = {'time': utc(), 'status': 'PASS' if result.wasSuccessful() else 'FAIL',
              'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
              'network': 'socket creation blocked', 'source_sha256': hashes,
              'log_sha256': hashlib.sha256(log_path.read_bytes()).hexdigest()}
    bundle = {'config_sha256': 'config/production_v1.json',
              'script_sha256': 'scripts/run_production.py',
              'criteria_sha256': 'docs/evidence_criteria.md', 'dashboard_sha256': 'dashboard.md'}
    if all((root / name).is_file() for name in bundle.values()):
        report['production_bundle_sha256'] = {
            key: hashlib.sha256((root / name).read_bytes()).hexdigest() for key, name in bundle.items()}
    agent_files = sorted((root / '.codex/agents').glob('*.toml'))
    if agent_files:
        agent_files += sorted((root / '.codex/hooks').glob('*.py'))
        agent_files += [root / name for name in ('.codex/hooks.json', '.codex/gold-registration.json',
                        '.codex/context.md', 'scripts/install_gold_pattern.py', 'scripts/verify_agent_smoke.py')]
        report['agent_bundle_sha256'] = {
            str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in agent_files if p.is_file()}
    write_json(out / 'offline_tests.json', report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), top_level_dir=str(root))
    stream = io.StringIO()
    with patch('socket.socket', side_effect=AssertionError('network forbidden in offline tests')):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    write_report(root / args.output, log, result, root)
    print(log)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
