"""Freeze the historical MVP T0 offline. Never fetches or executes T+7."""
import argparse
import hashlib
import json
import socket
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from money_trend.core import DataError, github_rows, parse_github, parse_hn, strict_json, utc, write_json

MVP_MANIFEST_SHA256 = 'e17335c5910f8f6b79bc8e39322fc84b0f72ebe3009f6dd1058bd40db8de0c99'
COHORT = [
    ('github', 'vercel/ai'), ('github', 'microsoft/ai-agents-for-beginners'),
    ('github', 'activepieces/activepieces'), ('github', 'FlowiseAI/Flowise'),
    ('github', 'reworkd/AgentGPT'), ('github', 'bojieli/ai-agent-book'),
    ('github', 'addyosmani/agent-skills'), ('github', 'zai-org/Open-AutoGLM'),
    ('github', 'ashishpatel26/500-AI-Agents-Projects'), ('github', 'NirDiamant/GenAI_Agents'),
    ('hn', '46990729'), ('hn', '48500012'), ('hn', '47460525'),
    ('hn', '46987559'), ('hn', '46515696')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    if path.stat().st_size > 4_000_000:
        raise DataError('baseline input exceeds byte budget')
    return strict_json(path.read_text(encoding='utf-8'))


def confined(parent, name):
    path = (parent / name).resolve()
    if not path.is_relative_to(parent.resolve()) or path.is_symlink():
        raise DataError('baseline input path escapes archive')
    return path


def counter(value, locator, missing_reason=None):
    """Preserve real zero; a missing counter remains null, never assumed zero."""
    if value is not None and (type(value) is not int or value < 0):
        raise DataError('invalid archived counter')
    return {'value': value, 'raw_locator': locator if value is not None else None,
            'missing_reason': missing_reason if value is None else None}


def build_rows(root):
    archive = root / 'artifacts/mvp-v1'
    manifest_path = archive / 'run_manifest.json'
    if sha(manifest_path) != MVP_MANIFEST_SHA256:
        raise DataError('original MVP manifest pin mismatch')
    manifest = load(manifest_path)
    for name, digest in manifest['artifacts_sha256'].items():
        if sha(confined(archive, name)) != digest:
            raise DataError('historical artifact hash mismatch: ' + name)
    ledger = load(archive / 'evidence_ledger.json')
    items = ledger['raw_items']
    if len(items) != 15 or [(r.get('source'), r.get('source_id')) for r in items] != COHORT:
        raise DataError('MVP cohort identity/order mismatch')
    if [r.get('evidence_id') for r in items] != [f'E{i:02d}' for i in range(1, 16)]:
        raise DataError('MVP evidence identity mismatch')
    sources = {}
    for source in ledger['sources']:
        path = confined(archive / 'requests', source['body_file'])
        meta = load(path.with_suffix('.meta.json'))
        if (sha(path) != source['sha256'] or meta['sha256'] != source['sha256']
                or meta['retrieved_at'] != source['retrieved_at'] or meta['url'] != source['url']
                or meta['status'] != 200 or meta['bytes'] != path.stat().st_size):
            raise DataError('MVP source metadata mismatch')
        body = path.read_text(encoding='utf-8')
        normalized = parse_github(body, limit=15) if source['source'] == 'github' else parse_hn(body, limit=15)
        raw = github_rows(body) if source['source'] == 'github' else strict_json(body)['hits']
        sources[source['source']] = {'source': source, 'path': path, 'normalized': normalized, 'raw': raw}
    if set(sources) != {'github', 'hn'}:
        raise DataError('both original sources required')
    rows = []
    for item in items:
        info = sources[item['source']]
        normalized = next((row for row in info['normalized'] if row['source_id'] == item['source_id']), None)
        if normalized is None or any(item.get(key) != value for key, value in normalized.items()):
            raise DataError('ledger record does not match parsed raw source')
        if (item['response_sha256'] != info['source']['sha256']
                or confined(archive, item['response_body']) != info['path']
                or item['retrieved_at'] != info['source']['retrieved_at']):
            raise DataError('record provenance does not match original response')
        t0 = datetime.fromisoformat(item['retrieved_at'])
        if t0.tzinfo is None or t0.date().isoformat() != '2026-11-02':
            raise DataError('unexpected T0 date/time')
        if item['source'] == 'github':
            matches = [(i, row) for i, row in enumerate(info['raw'])
                       if row.get('repo', {}).get('repository', {}).get('owner_login', '') + '/'
                       + row.get('repo', {}).get('repository', {}).get('name', '') == item['source_id']]
            if len(matches) != 1:
                raise DataError('repo raw identity/locator is ambiguous')
            index, raw = matches[0]
            prefix = f'payload.blackbirdSearchRoute.results[{index}]'
            counters = {field: counter(raw.get(field), prefix + '.' + field, 'FIELD_NOT_PRESENT_AT_T0')
                        for field in ('followers', 'help_wanted_issues_count', 'good_first_issue_issues_count')}
            counters.update(stargazers_count=counter(None, None, 'NO_VERIFIED_STAR_COUNTER_AT_T0'),
                            total_issues=counter(None, None, 'NO_TOTAL_ISSUE_COUNTER_AT_T0'),
                            issue_comments=counter(None, None, 'NO_SPECIFIC_ISSUE_IDS_IN_MVP_COHORT'))
            gaps = ['NO_VERIFIED_STAR_COUNTER_AT_T0', 'NO_TOTAL_ISSUE_COUNTER_AT_T0',
                    'NO_SPECIFIC_ISSUE_IDS_IN_MVP_COHORT', 'FOLLOWERS_SEMANTICS_NOT_VERIFIED_AS_STARS']
        else:
            matches = [(i, row) for i, row in enumerate(info['raw']) if row.get('objectID') == item['source_id']]
            if len(matches) != 1:
                raise DataError('HN raw identity/locator is ambiguous')
            index, raw = matches[0]
            prefix = f'hits[{index}]'
            counters = {field: counter(raw.get(field), prefix + '.' + field, 'FIELD_NOT_PRESENT_AT_T0')
                        for field in ('points', 'num_comments')}
            gaps = ['COMMENT_COUNTER_DELTA_IS_NET_NOT_NEW_COMMENT_EVENTS']
        rows.append({'evidence_id': item['evidence_id'], 'source': item['source'],
                     'stable_id': item['source_id'], 'original_record': item,
                     'original_t0': item['retrieved_at'], 'scheduled_t7': (t0 + timedelta(days=7)).isoformat(),
                     'scheduled_t14': (t0 + timedelta(days=14)).isoformat(),
                     'source_request_url': info['source']['url'], 'raw_locator': prefix,
                     'raw_response_path': info['path'].relative_to(root).as_posix(),
                     'raw_response_sha256': item['response_sha256'], 'counters': counters,
                     'followup_observed_at': None, 'followup_counters': None, 'delta': None,
                     'comparable': False, 'trend_evidence_present': False,
                     'gaps': gaps + ['T7_T14_NOT_OBSERVED', 'TREND_PROTOCOL_REGISTERED_AFTER_ORIGINAL_T0']})
    return rows, manifest


def prepare(root=ROOT):
    root = Path(root).resolve()
    out = root / 'artifacts/t7-baseline'
    if out.exists():
        raise FileExistsError('T0 baseline already exists; historical baseline cannot be overwritten')
    rows, original_manifest = build_rows(root)
    # The output is created only after every original input passes validation.
    out.mkdir(parents=True, exist_ok=False)
    snapshot = out / 'snapshot_t0.jsonl'
    snapshot.write_bytes(''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n'
                                 for row in rows).encode('utf-8'))
    note = '''# T+7 baseline — offline preparation only

15 frozen records: 10 GitHub repositories and 5 HN stories, from the original
MVP live run on 02/11/2026. Preparation time is not a new observation time.
Original raw bytes, IDs, timestamps and counter locators are referenced; no
network requests or T+7/T+14 measurements were made by this script.

HN points/num_comments exist for all 5 stories. GitHub followers and two labeled
issue counters are retained literally. Followers are not asserted to be stars.
Verified GitHub stars, total issues and specific issue comment baselines are
missing/null. Null is not zero. New issue/comment events cannot be inferred
from those fields. Future counter changes are net deltas, not new event counts.

T+7 target: 09/11/2026; T+14:16/11/2026, preserving each original UTC anchor.
No scheduler/cron/follow-up approval is created. A future run must preserve the
15 IDs, verify method/field compatibility, retain missing rows, and keep absent
values/deltas null. Current trend_evidence_present=false for every member.
This retrospective registration is not a pre-T0 trend protocol.

See docs/t7_plan.md for metrics, sampling, target windows and limitations.
Missing GitHub metrics need a separately timestamped, approved future baseline;
they cannot be backfilled as observations from the original T0.
'''
    (out / 'README.md').write_bytes(note.encode('utf-8'))
    manifest = {'status': 'BASELINE_PREPARED_WITH_GAPS', 'run_kind': 'offline_historical_t0_freeze',
                'prepared_at': utc(), 'network_requests': 0, 't7_executed': False, 't14_executed': False,
                'raw_count': len(rows), 'source_counts': original_manifest['source_counts'],
                'original_manifest': 'artifacts/mvp-v1/run_manifest.json',
                'original_manifest_sha256': MVP_MANIFEST_SHA256,
                'original_artifacts_sha256': original_manifest['artifacts_sha256'],
                'script_sha256': sha(Path(__file__)),
                'cohort_sha256': hashlib.sha256(json.dumps(COHORT, separators=(',', ':')).encode()).hexdigest(),
                'gaps': ['NO_VERIFIED_GITHUB_STAR_COUNTER_AT_T0', 'NO_TOTAL_GITHUB_ISSUE_COUNTER_AT_T0',
                         'NO_GITHUB_ISSUE_IDS_IN_COHORT', 'T7_T14_NOT_OBSERVED',
                         'TREND_PROTOCOL_REGISTERED_AFTER_ORIGINAL_T0'],
                'artifacts_sha256': {p.name: sha(p) for p in (snapshot, out / 'README.md')}}
    write_json(out / 'run_manifest.json', manifest)
    return out


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    with patch.object(socket, 'socket', side_effect=AssertionError('T0 preparation forbids network')):
        output = prepare()
    print(json.dumps({'status': 'BASELINE_PREPARED_WITH_GAPS', 'records': 15,
                      'network_requests': 0, 't7_executed': False, 'output': str(output)}))
