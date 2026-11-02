"""Explicit one-shot live RSS retry; output directory and consumed flag prevent replay."""
import json
import socket
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from money_trend.indie_retry import capture, report


if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('--capture', '--report'):
        raise SystemExit('--capture requires one-batch approval; --report only finalizes saved failed capture offline.')
    if sys.argv[1] == '--report':
        with patch.object(socket, 'socket', side_effect=AssertionError('offline report forbids network')):
            result = report(ROOT)
        print(json.dumps({k: result[k] for k in ('status', 'source_reliability', 'request_attempts', 'opportunities', 'baseline_records', 'offline_tests')}))
    else:
        result = capture(ROOT)
        print(json.dumps({'source_reliability': result['source_reliability'], 'request_attempts': result['request_attempts'],
                          'outcomes': [{'keyword': r['keyword'], 'http_status': r['http_status'], 'state': r['state']} for r in result['outcomes']],
                          'retained_records': len(result['records'])}))
