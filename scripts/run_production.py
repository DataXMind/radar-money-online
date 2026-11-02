"""Approval-gated, offline-only draft reporting. No live client is invoked."""
import argparse
import csv
import hashlib
import io
import json
import re
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from money_trend.core import DataError, parse_github, parse_hn, strict_json, utc, write_json
from money_trend.pipeline import claims_for, gate

REQUIRED = ['buyer_evidence', 'payment_evidence', 'trend_evidence']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confined(value, parent):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(parent.resolve()):
        raise DataError('path outside permitted directory')
    return path


def load(path, limit=4_000_000):
    if path.stat().st_size > limit:
        raise DataError('input exceeds size budget')
    return strict_json(path.read_text(encoding='utf-8'))


def source_hashes():
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
            for folder in ('money_trend', 'tests') for p in sorted((ROOT / folder).rglob('*.py'))}


def validate_config(config):
    if (not isinstance(config, dict) or config.get('execution_mode') != 'HUMAN_APPROVAL_REQUIRED'
            or config.get('option') != 'B' or config.get('network_enabled') is not False
            or type(config.get('window_days')) is not int or config['window_days'] != 7
            or config.get('required_evidence') != REQUIRED
            or config.get('output_root') != 'artifacts/production-v1'):
        raise DataError('only approval-gated offline option B is supported')
    limits = config.get('limits')
    if (not isinstance(limits, dict) or set(limits) != {'raw_items', 'claims', 'opportunities'}
            or any(type(limits[k]) is not int or not 1 <= limits[k] <= cap
                   for k, cap in [('raw_items', 15), ('claims', 8), ('opportunities', 5)])):
        raise DataError('invalid limits')


def approval_bindings(config_path, config):
    paths = {
        'config_sha256': config_path,
        'script_sha256': Path(__file__),
        'criteria_sha256': confined(config['criteria_file'], ROOT / 'docs'),
        'test_report_sha256': confined(config['test_report'], ROOT / 'artifacts'),
        'dashboard_sha256': confined(config['dashboard_template'], ROOT),
    }
    return {key: sha(path) for key, path in paths.items()}


def parse_time(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if result.tzinfo is None:
            raise ValueError('timezone required')
        return result
    except (ValueError, TypeError, AttributeError) as exc:
        raise DataError('invalid timestamp') from exc


def preflight(config_path, approval_path, run_id, now):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', run_id):
        raise DataError('unsafe run ID')
    config_path = confined(config_path, ROOT / 'config')
    config = load(config_path)
    validate_config(config)
    bindings = approval_bindings(config_path, config)
    if bindings['criteria_sha256'] != config['criteria_sha256']:
        raise DataError('criteria changed; review and rebind config first')
    report = load(confined(config['test_report'], ROOT / 'artifacts'))
    if (not isinstance(report, dict) or report.get('status') != 'PASS'
            or type(report.get('tests_run')) is not int or report['tests_run'] < 1
            or report.get('failures') != 0 or report.get('errors') != 0
            or report.get('source_sha256') != source_hashes()
            or report.get('production_bundle_sha256') != {
                k: v for k, v in bindings.items() if k != 'test_report_sha256'}):
        raise DataError('current passing offline test report required')
    log_path = confined(config['test_report'], ROOT / 'artifacts').with_name('offline_tests.txt')
    if sha(log_path) != report.get('log_sha256'):
        raise DataError('test log hash mismatch')
    approval = load(confined(approval_path, ROOT / 'config' / 'approvals'))
    if (not isinstance(approval, dict) or approval.get('approved') is not True
            or approval.get('action') != 'RUN_OFFLINE_DRAFT' or approval.get('run_id') != run_id
            or not isinstance(approval.get('reviewer'), str) or not approval['reviewer'].strip()
            or any(approval.get(k) != v for k, v in bindings.items())
            or approval.get('output_root') != config['output_root']):
        raise DataError('explicit human approval matching this run and bundle is required')
    approved_at = parse_time(approval.get('approved_at'))
    if not now - timedelta(hours=24) <= approved_at <= now:
        raise DataError('approval expired or future-dated')
    return config, bindings, approval


def evidence_gaps(candidate):
    """Necessary conditions only; summary booleans never authorize qualification."""
    gaps = []
    for name in REQUIRED:
        proof = candidate.get(name) if isinstance(candidate, dict) else None
        fields = ('cohort', 't0', 't_plus', 'metric') if name == 'trend_evidence' else ('proof_type', 'url')
        if (not isinstance(proof, dict) or proof.get('present') is not True
                or any(not isinstance(proof.get(k), str) or not proof[k].strip() for k in fields)):
            gaps.append('MISSING_' + name.upper())
    # No positive qualification path in option B, even with all summaries present.
    return gaps + ['OPTION_B_KEEP_DRAFT: proof verification and qualification remain unavailable']


def read_archive(config, now, log):
    manifest_path = confined(config['input_manifest'], ROOT / 'artifacts')
    if sha(manifest_path) != config['input_manifest_sha256']:
        raise DataError('archive manifest hash mismatch')
    manifest = load(manifest_path)
    ledger_path = manifest_path.parent / 'evidence_ledger.json'
    if sha(ledger_path) != manifest['artifacts_sha256']['evidence_ledger.json']:
        raise DataError('archive ledger hash mismatch')
    ledger = load(ledger_path)
    items, errors, seen = [], [], set()
    for source in ledger['sources']:
        name = source['source']
        if name not in ('github', 'hn') or name in seen:
            raise DataError('unknown or duplicate archive source')
        seen.add(name)
        raw_path = (manifest_path.parent / 'requests' / source['body_file']).resolve()
        if not raw_path.is_relative_to((manifest_path.parent / 'requests').resolve()):
            raise DataError('unsafe archive body path')
        if raw_path.stat().st_size > 4_000_000 or sha(raw_path) != source['sha256']:
            raise DataError('archive body integrity failure')
        retrieved = parse_time(source['retrieved_at'])
        log('archive_ingress', source=name, sha256=source['sha256'], retrieved_at=source['retrieved_at'])
        if not now - timedelta(days=7) <= retrieved <= now:
            errors.append('STALE_OR_FUTURE_ARCHIVE: ' + name)
            continue
        parser, limit = (parse_github, 10) if name == 'github' else (parse_hn, 5)
        parsed = parser(raw_path.read_bytes().decode('utf-8'), limit=limit)
        for item in parsed:
            item.update(evidence_id=f'E{len(items)+1:02d}', response_sha256=source['sha256'],
                        response_body=str(raw_path.relative_to(ROOT)).replace('\\', '/'),
                        retrieved_at=source['retrieved_at'])
            items.append(item)
        log('archive_validation_pass', source=name, count=len(parsed))
    return items[:config['limits']['raw_items']], errors


def execute(config_path, approval_path, run_id):
    """Called only after a separate human decision. Tests use temporary directories."""
    now = datetime.now(timezone.utc)
    config, bindings, approval = preflight(config_path, approval_path, run_id, now)
    out = ROOT / config['output_root'] / run_id
    out.mkdir(parents=True, exist_ok=False)
    def log(event, **fields):
        with (out / 'ingress.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time': utc(), 'event': event, **fields}) + '\n')
    log('approved_config_ingress', **bindings, reviewer=approval['reviewer'])
    write_json(out / 'checkpoint.json', {'state': 'started', 'run_id': run_id})
    items, errors = [], []
    try:
        # Defense in depth: no accidental network even if an adapter is changed later.
        with patch.object(socket, 'socket', side_effect=DataError('network disabled in option B')):
            items, errors = read_archive(config, now, log)
    except (DataError, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
        errors.append('ARCHIVE_INGRESS_ERROR: ' + str(exc))
        log('archive_validation_fail', error=str(exc))
    claims = claims_for(items)[:config['limits']['claims']]
    decision = gate(items, errors)
    gaps = evidence_gaps({})
    reasons = decision['kill_reasons'] + gaps
    ledger = {'run_kind': 'offline_archive_replay', 'raw_items': items, 'claims': claims,
              'status': decision['status'], 'opportunities': [], 'kill_reasons': reasons}
    write_json(out / 'evidence_ledger.json', ledger)
    stream = io.StringIO(newline='')
    csv.writer(stream).writerow(['opportunity_id', 'title', 'buyer_evidence', 'payment_evidence', 'trend_evidence', 'verdict'])
    (out / 'opportunities.csv').write_bytes(stream.getvalue().encode())
    values = dict(run_id=run_id, generated_at=utc(), status=decision['status'], raw_count=len(items),
                  claim_count=len(claims), opportunity_count=0, top_rows='No eligible opportunities.',
                  gap_summary='\n'.join('- ' + reason for reason in reasons))
    template = confined(config['dashboard_template'], ROOT).read_text(encoding='utf-8')
    (out / 'dashboard.md').write_bytes(template.format_map(values).encode('utf-8'))
    write_json(out / 'checkpoint.json', {'state': 'stopped', 'status': decision['status']})
    log('run_stopped', status=decision['status'])
    write_json(out / 'run_manifest.json', {'run_id': run_id, 'run_kind': 'offline_archive_replay',
               'execution_mode': config['execution_mode'], 'network_enabled': False, 'window_days': 7,
               'status': decision['status'], 'raw_count': len(items), 'claim_count': len(claims),
               'opportunity_count': 0, 'opportunities': [], 'kill_reasons': reasons,
               'approval': approval, 'input_bindings': bindings, 'source_sha256': source_hashes(),
               'archive_manifest_sha256': config['input_manifest_sha256'],
               'artifacts_sha256': {p.name: sha(p) for p in out.iterdir() if p.is_file()}})
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='config/production_v1.json')
    parser.add_argument('--approval-file', required=True)
    parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    try:
        out = execute(args.config, args.approval_file, args.run_id)
    except (DataError, OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f'Blocked: {exc}\n')
    print('RESEARCH_DRAFT_ONLY:', out)


if __name__ == '__main__':
    main()
