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
