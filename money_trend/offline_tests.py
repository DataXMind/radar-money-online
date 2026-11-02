"""Offline runner: block all sockets; write a verifiable current-source report."""
import hashlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from .core import utc, write_json


def main():
    root = Path(__file__).resolve().parents[1]
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), top_level_dir=str(root))
    stream = io.StringIO()
    with patch('socket.socket', side_effect=AssertionError('network forbidden in offline tests')):
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    log = stream.getvalue()
    out = root / 'artifacts'
    out.mkdir(exist_ok=True)
    (out / 'offline_tests.txt').write_text(log, encoding='utf-8')
    hashes = {str(p.relative_to(root)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
              for folder in ('money_trend', 'tests') for p in sorted((root / folder).rglob('*.py'))}
    write_json(out / 'offline_tests.json', {'time': utc(), 'status': 'PASS' if result.wasSuccessful() else 'FAIL',
               'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
               'network': 'socket creation blocked', 'source_sha256': hashes,
               'log_sha256': hashlib.sha256(log.encode('utf-8')).hexdigest()})
    print(log)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
