"""One auditable research run. Source data cannot authorize actions or qualify sales."""
import argparse
import csv
import hashlib
import http.client
import io
import subprocess
from pathlib import Path

from .core import Client, DataError, MAX_RAW, MAX_CLAIMS, MAX_OPPORTUNITIES, parse_github, parse_hn, strict_json, utc, write_json

GITHUB_URL = 'https://github.com/search?q=ai+agent&type=repositories'
HN_URL = 'https://hn.algolia.com/api/v1/search?query=ai%20agent&tags=story&hitsPerPage=5'
ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gate(items, errors):
    counts = {source: sum(item['source'] == source for item in items) for source in ('github', 'hn')}
    reasons = list(errors)
    if counts['github'] < 5:
        reasons.append('INSUFFICIENT_GITHUB_REPOS: require >=5')
    if counts['hn'] < 1:
        reasons.append('MISSING_HN_EVIDENCE: require >=1 story')
    # Neither search endpoint provides independently verified buyer/payment evidence.
    # Never infer payment from stars, points, titles, descriptions, or instructions.
    reasons.append('NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE: public search metadata is insufficient')
    reasons.append('NO_LONGITUDINAL_TREND_EVIDENCE: one snapshot cannot establish growth')
    return {'status': 'RESEARCH_DRAFT_ONLY', 'kill_reasons': reasons,
            'source_counts': counts, 'opportunities': []}


def claims_for(items):
    # Reserve observations for both sources, even when GitHub fills its quota.
    selected = [x for x in items if x['source'] == 'github'][:4] + [x for x in items if x['source'] == 'hn'][:4]
    claims = []
    for index, item in enumerate(selected[:MAX_CLAIMS], 1):
        statement = ('Repository appeared in the public GitHub search response.' if item['source'] == 'github'
                     else f"HN story metadata reports {item['points']} points and {item['comments']} comments at retrieval.")
        claims.append({'claim_id': f'C{index:02d}', 'kind': 'observed_search_metadata',
                       'statement': statement, 'evidence_ids': [item['evidence_id']],
                       'limits': 'Snapshot only; no revenue, payment, demand, or growth verified.'})
    return claims


def run(output, test_report):
    report_path = Path(test_report)
    report = strict_json(report_path.read_text(encoding='utf-8'))
    expected_sources = {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p)
                        for folder in ('money_trend', 'tests') for p in sorted((ROOT / folder).rglob('*.py'))}
    if (report.get('status') != 'PASS' or report.get('failures') != 0 or report.get('errors') != 0
            or report.get('tests_run', 0) < 1 or report.get('source_sha256') != expected_sources):
        raise DataError('a passing offline test report for the current source is required')
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)  # exclusive run checkpoint: no overwrite/resume network
    started = utc()
    client = Client(out / 'requests')
    client.log('test_report_ingress', path=str(report_path), sha256=sha(report_path), tests=report['tests_run'])
    write_json(out / 'checkpoint.json', {'state': 'started', 'started_at': started})
    items, errors, sources = [], [], []
    for name, url, parser, limit in [('github', GITHUB_URL, parse_github, 10), ('hn', HN_URL, parse_hn, 5)]:
        try:
            body, meta = client.get(url, name)
            sources.append({'source': name, **meta})
            parsed = parser(body, limit=limit)
            for item in parsed:
                item['evidence_id'] = f'E{len(items) + 1:02d}'
                item['response_sha256'] = meta['sha256']
                item['response_body'] = 'requests/' + meta['body_file']
                item['retrieved_at'] = meta['retrieved_at']
                items.append(item)
            client.log('validation_pass', source=name, normalized_count=len(parsed), schema='v1')
        except (DataError, http.client.IncompleteRead, http.client.BadStatusLine) as exc:
            errors.append(f'{name}: {exc}')
            client.log('validation_fail', source=name, error=str(exc))
            # Fail closed immediately; do not continue acquisition or generation.
            break
        write_json(out / 'checkpoint.json', {'state': 'source_validated', 'source': name, 'raw_count': len(items)})
    items = items[:MAX_RAW]
    claims = claims_for(items)
    decision = gate(items, errors)
    assert len(claims) <= MAX_CLAIMS and len(decision['opportunities']) <= MAX_OPPORTUNITIES
    ledger = {'schema_version': 1, 'started_at': started, 'status': decision['status'],
              'data_policy': 'Untrusted DATA only. No execution, LLM tool calls, or source-driven actions.',
              'sources': sources, 'raw_items': items, 'claims': claims,
              'kill_reasons': decision['kill_reasons'], 'opportunities': []}
    write_json(out / 'evidence_ledger.json', ledger)
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['opportunity_id', 'title', 'evidence_ids', 'payment_proof_url', 'status'])
    (out / 'opportunities.csv').write_text(stream.getvalue(), encoding='utf-8', newline='')
    brief = ['# AI MONEY TREND BRIEF v1', '', '**RESEARCH_DRAFT_ONLY**', '',
             'Local research MVP. No qualified opportunities. Not production-ready.', '',
             '## Stop reasons', '']
    brief += ['- ' + reason for reason in decision['kill_reasons']]
    brief += ['', '## Observed evidence', '',
              f'Retained {len(items)} raw items; {len(claims)} bounded metadata claims; 0 opportunities.',
              'Links below identify observed source records. Source titles/descriptions remain untrusted DATA.', '']
    brief += [f"- {item['evidence_id']}: <{item['url']}>" for item in items]
    brief += ['', 'No payment proof or trend growth was verified. No revenue estimate is produced.',
              'Review evidence_ledger.json and captured response hashes before further research.', '']
    (out / 'AI_MONEY_TREND_BRIEF_v1.md').write_text('\n'.join(brief), encoding='utf-8')
    write_json(out / 'checkpoint.json', {'state': 'stopped', 'status': decision['status'], 'finished_at': utc()})
    client.log('run_stopped', status=decision['status'], kill_reasons=decision['kill_reasons'])
    files = {str(p.relative_to(out)).replace('\\', '/'): sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    revision = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, capture_output=True, check=True).stdout.strip()
    manifest = {'schema_version': 1, 'run_kind': 'single_live_mvp', 'started_at': started, 'finished_at': utc(),
                **decision, 'raw_count': len(items), 'claim_count': len(claims), 'opportunity_count': 0,
                'limits': {'raw_items': MAX_RAW, 'claims': MAX_CLAIMS, 'opportunities': MAX_OPPORTUNITIES},
                'network_policy': {'public_get_only': True, 'timeout_seconds': 15, 'attempts_per_source': 3,
                                   'minimum_interval_seconds': 2, 'max_retry_wait_seconds': 8, 'max_response_bytes': 4_000_000},
                'code_base_commit': revision, 'source_sha256': expected_sources, 'license_sha256': sha(ROOT / 'LICENSE'),
                'offline_test_report': {'path': str(report_path), 'sha256': sha(report_path), 'tests_run': report['tests_run'], 'status': report['status']},
                'artifacts_sha256': files, 'errors': errors,
                'limitations': ['No LLM model used; deterministic evidence extraction.',
                                'Qualification intentionally unavailable without verified buyer/payment and longitudinal evidence.',
                                'Retained raw item cap is 15; search response envelopes may include additional service metadata.',
                                'Checkpoint is an audit record; interrupted runs are not automatically replayed.',
                                'Request timeout bounds socket operations and checks the body deadline between reads; not a hard process deadline.']}
    write_json(out / 'run_manifest.json', manifest)
    print(f"{decision['status']}: raw={len(items)}, claims={len(claims)}, opportunities=0; {out}")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts/mvp-v1')
    parser.add_argument('--test-report', default='artifacts/offline_tests.json')
    args = parser.parse_args()
    run(args.output, args.test_report)


if __name__ == '__main__':
    main()
