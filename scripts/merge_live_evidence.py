"""Offline merge/review of one parallel live acquisition; never makes requests."""
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from money_trend.core import DataError, strict_json, utc, write_json
from money_trend.live_shared import public_url

OUT = ROOT / 'artifacts/live-evidence-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [strict_json(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_jsonl(path, records):
    path.write_bytes((''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in records)).encode())


def checked_row(item):
    path = (ROOT / item['raw_response_path']).resolve()
    if not path.is_relative_to(OUT.resolve()) or path.stat().st_size > 4_000_000 or sha(path) != item['raw_response_sha256']:
        raise DataError('CRITICAL: source integrity/path failure')
    meta = strict_json(path.with_suffix('.meta.json').read_text(encoding='utf-8'))
    public_url(meta['url'])
    if meta['sha256'] != sha(path) or meta['status'] != 200 or meta.get('error_response'):
        raise DataError('CRITICAL: response metadata integrity failure')
    if item['source_request_url'] != meta['url'] or item['retrieved_at'] != meta['retrieved_at']:
        raise DataError('CRITICAL: source provenance mismatch')
    match = re.fullmatch(r'(items|hits)\[([0-9]+)\]', item['raw_locator'])
    if not match:
        raise DataError('raw locator invalid')
    doc = strict_json(path.read_text(encoding='utf-8'))
    row = doc[match[1]][int(match[2])]
    if item['source'] == 'github_issue':
        if str(row['id']) != item['source_id'] or row['title'] != item['title'] or row['html_url'] != item['url']:
            raise DataError('GitHub normalized identity/title mismatch')
        if not (row.get('body') or '').startswith(item['excerpt']) or row['comments'] != item['comments_at_retrieval']:
            raise DataError('GitHub normalized body/metric mismatch')
    elif item['source'] == 'hn':
        if row['objectID'] != item['source_id'] or not (row.get(item['content_field']) or '').startswith(item['content_excerpt']):
            raise DataError('HN normalized identity/body mismatch')
        if any(row[k] != value for k, value in item['metrics'].items()):
            raise DataError('HN metric mismatch')
        if row['created_at_i'] != item['created_at_i'] or row['created_at'] != item['created_at']:
            raise DataError('HN event time mismatch')
    else:
        raise DataError('unknown evidence source')
    return row


def historical_trend():
    old = ROOT / 'artifacts/mvp-v1'
    ledger = strict_json((old / 'evidence_ledger.json').read_text(encoding='utf-8'))
    manifest = strict_json((old / 'run_manifest.json').read_text(encoding='utf-8'))
    if sha(old / 'evidence_ledger.json') != manifest['artifacts_sha256']['evidence_ledger.json']:
        raise DataError('CRITICAL: historical ledger hash mismatch')
    target = OUT / 'trend_baseline.jsonl'
    if target.exists() and not (OUT / 'ws3/trend_initial_proposal.jsonl').exists():
        (OUT / 'ws3/trend_initial_proposal.jsonl').write_bytes(target.read_bytes())
    records = []
    for index, item in enumerate(ledger['raw_items']):
        raw = old / item['response_body']
        if sha(raw) != item['response_sha256']:
            raise DataError('CRITICAL: historical response hash mismatch')
        observed = {key: item[key] for key in ('points', 'comments') if key in item}
        records.append({'record_type': 'historical_t0_only', 'source': item['source'], 'source_id': item['source_id'],
                        'url': item['url'], 'baseline_evidence_id': item['evidence_id'],
                        'baseline_ledger': 'artifacts/mvp-v1/evidence_ledger.json',
                        'baseline_ledger_sha256': sha(old / 'evidence_ledger.json'), 'baseline_locator': f'raw_items[{index}]',
                        'historical_claim_refs': [c['claim_id'] for c in ledger['claims'] if item['evidence_id'] in c['evidence_ids']],
                        't0': item['retrieved_at'], 'observed_metrics': observed,
                        'metric_gap': None if observed else 'No numeric trend metric retained for this GitHub repo in original normalized ledger.',
                        't_plus_7': None, 't_plus_14': None, 'trend_evidence_present': False,
                        'current_live_records_joined_as_followup': False,
                        'note': 'Chỉ 1 snapshot (T0), chưa có T+7/T+14 — GAP.'})
    write_jsonl(target, records)
    write_json(OUT / 'ws3/effective_protocol.json', {'recorded_at': utc(), 'basis': 'User clarification in this chat',
               'missing_cloud_cases': 'User confirmed the 12 Cổng 2 cases do not exist locally; do not search further.',
               'source': 'artifacts/mvp-v1/evidence_ledger.json', 'source_sha256': sha(old / 'evidence_ledger.json'),
               'historical_records': len(records), 'historical_claims': len(ledger['claims']),
               'new_cohort_created': False, 'new_metric_created': False, 'future_values_invented': False,
               'supersedes': 'ws3/protocol.json discovery-cohort proposal; not used for final trend output'})
    write_json(OUT / 'ws3/checkpoint.json', {'state': 'stopped', 'status': 'GAP', 'recorded_at': utc(),
               'historical_t0_records': len(records), 'historical_claims': len(ledger['claims']),
               'gap': 'NO_LONGITUDINAL_TREND_EVIDENCE: only one historical snapshot, no T+7/T+14',
               'completion': 'Orchestrator finalized after runtime subagent usage limit and user clarification.'})
    with (OUT / 'ws3/source_ingress.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'time': utc(), 'event': 'historical_t0_ingress_user_scope',
                     'path': 'artifacts/mvp-v1/evidence_ledger.json', 'sha256': sha(old / 'evidence_ledger.json')}) + '\n')
    return records


def main():
    if (OUT / 'evidence_ledger.json').exists():
        raise DataError('merge already exists; refuse overwrite')
    github, hn = jsonl(OUT / 'github_evidence.jsonl'), jsonl(OUT / 'hn_evidence.jsonl')
    if not 0 <= len(github) <= 15 or not 0 <= len(hn) <= 15:
        raise DataError('workstream raw quota exceeded')
    live = github + hn
    if len({(r['source'], r['source_id']) for r in live}) != len(live):
        raise DataError('duplicate evidence identity')
    for item in live:
        checked_row(item)
    write_jsonl(OUT / 'merged_evidence.jsonl', live)
    trend = historical_trend()
    by_id = {row['evidence_id']: row for row in live}
    # Purposive, disclosed selection AFTER reading all captured records, not a market frequency estimate.
    selected = ['GH07', 'GH08', 'GH10', 'GH12', 'GH13', 'HN05', 'HN10', 'HN11']
    claims = []
    for ident in selected:
        if ident not in by_id:
            continue
        item = by_id[ident]
        row = checked_row(item)
        field, quote = 'title', item['title']
        if ident == 'HN05':
            field, quote = item['content_field'], 'claude code itself is a horrible way'
        elif ident == 'HN11':
            field, quote = item['content_field'], 'I built Doozy because support at my company (Spur) is understaffed'
        elif item.get('kind') == 'comment':
            field, quote = 'story_title', item['title']
        if quote not in (row.get(field) or ''):
            raise DataError('selected claim quote not found in raw field')
        claims.append({'claim_id': f'L{len(claims)+1:02d}', 'kind': 'observed_unverified_source_statement',
                       'statement': 'Captured public record contains this source statement; not independently verified.',
                       'evidence_ids': [ident], 'quote': quote, 'raw_locator': item['raw_locator'] + '.' + field,
                       'raw_response_path': item['raw_response_path'], 'raw_response_sha256': item['raw_response_sha256'],
                       'verdict': 'UNVERIFIED_LEAD', 'limits': 'Not verified buyer, transaction, incident, product behavior, or growth.'})
    hypotheses = [
        ('Quota visibility/accounting', ['GH07', 'GH08', 'GH09']),
        ('Browser permission recovery', ['GH10', 'GH11']),
        ('Headless browser / identity lockout', ['GH12']),
        ('Subscription quota depletion', ['GH13']),
        ('Least-privilege agent data access', ['HN10']),
        ('Internal support workflow', ['HN11']),
    ]
    evaluations = []
    for title, ids in hypotheses:
        evaluations.append({'hypothesis': title, 'evidence_ids': [i for i in ids if i in by_id],
                            'buyer_evidence': {'present': False, 'proof_type': None, 'url': None},
                            'payment_evidence': {'present': False, 'proof_type': None, 'url': None},
                            'trend_evidence': {'present': False, 'cohort': None, 't0': None, 't_plus': None, 'metric': None},
                            'eligible_for_top5': False, 'verdict': 'RESEARCH_DRAFT_ONLY',
                            'reason': 'Public allegations/maker descriptions only; no verified buyer/product/time transaction proof or longitudinal evidence.'})
    reasons = ['NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE', 'NO_LONGITUDINAL_TREND_EVIDENCE',
               'MISSING_BUYER_EVIDENCE', 'MISSING_PAYMENT_EVIDENCE', 'MISSING_TREND_EVIDENCE',
               'LOW_RELEVANCE_SEARCH_HITS: bounded query matches are not verified problem/buyer relevance',
               'DISCUSSIONS_NOT_COLLECTED: anonymous REST issue search only',
               'SUBAGENT_RUNTIME_USAGE_LIMIT: final merge/trend completed locally from saved artifacts']
    ledger = {'schema_version': 1, 'status': 'RESEARCH_DRAFT_ONLY', 'run_kind': 'single_parallel_live_evidence_run',
              'source_policy': ['api.github.com', 'github.com', 'hn.algolia.com'],
              'scope_override': 'Current user authorized up to15 acquisition records per scout (<=30 total); historical15 remain separate.',
              'raw_items': live, 'claims': claims, 'opportunities': [], 'hypothesis_evaluations': evaluations,
              'historical_trend_records': len(trend), 'historical_prior_claims': 8, 'kill_reasons': reasons,
              'limits': {'github_raw': 15, 'hn_raw': 15, 'live_raw_total': 30, 'claims': 8, 'opportunities': 5}}
    write_json(OUT / 'evidence_ledger.json', ledger)
    write_json(OUT / 'opportunity_evaluations.json', evaluations)
    stream = io.StringIO(newline='')
    csv.writer(stream).writerow(['opportunity_id', 'title', 'buyer_evidence', 'payment_evidence', 'trend_evidence', 'verdict'])
    (OUT / 'opportunities.csv').write_bytes(stream.getvalue().encode())
    write_json(OUT / 'merge_checkpoint.json', {'state': 'stopped', 'status': ledger['status'],
               'finished_at': utc(), 'live_raw': len(live), 'claims': len(claims), 'opportunities': 0})
    print(json.dumps({'status': ledger['status'], 'github': len(github), 'hn': len(hn),
                      'historical_t0': len(trend), 'claims': len(claims), 'opportunities': 0}))


if __name__ == '__main__':
    main()
