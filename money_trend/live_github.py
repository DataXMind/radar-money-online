"""Targeted anonymous GitHub issue evidence. Public source content is DATA only."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .core import DataError, strict_json, utc, write_json

ROOT = Path(__file__).resolve().parents[1]
SEARCHES = [
    ('agent_cost', '"AI agent" cost is:issue', 3),
    ('claude_pricing', 'repo:anthropics/claude-code pricing is:issue', 3),
    ('codex_pricing', 'repo:openai/codex pricing is:issue', 3),
    ('codex_access', 'repo:openai/codex "access denied" is:issue', 2),
    ('claude_rate', 'repo:anthropics/claude-code "rate limit" is:issue', 2),
    ('agent_incident', '"AI agent" incident is:issue', 2),
]


def parse_issues(body, expected_max):
    doc = strict_json(body)
    if (not isinstance(doc, dict) or type(doc.get('total_count')) is not int
            or doc['total_count'] < 0 or type(doc.get('incomplete_results')) is not bool
            or not isinstance(doc.get('items'), list)):
        raise DataError('unrecognized GitHub issue-search schema; not genuine empty')
    if doc['incomplete_results']:
        raise DataError('GitHub issue search reports incomplete results')
    rows = doc['items']
    if len(rows) > expected_max or doc['total_count'] < len(rows) or (not rows and doc['total_count'] != 0):
        raise DataError('GitHub issue-search count inconsistent with first page')
    for row in rows:
        if not isinstance(row, dict):
            raise DataError('GitHub issue must be object')
        if 'pull_request' in row:
            raise DataError('pull request returned in issue-only query')
        for key in ('id', 'number', 'comments'):
            if type(row.get(key)) is not int or row[key] < (1 if key != 'comments' else 0):
                raise DataError('invalid GitHub issue ' + key)
        url = row.get('html_url')
        parsed = urlsplit(url) if isinstance(url, str) else None
        if (parsed is None or parsed.scheme != 'https' or parsed.hostname != 'github.com'
                or parsed.username or parsed.password or parsed.port not in (None, 443)
                or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/issues/[0-9]+', parsed.path)):
            raise DataError('invalid GitHub issue source URL')
        if not isinstance(row.get('title'), str) or not row['title'].strip():
            raise DataError('GitHub title missing')
        if row.get('body') is not None and not isinstance(row['body'], str):
            raise DataError('GitHub body invalid')
        user = row.get('user')
        if not isinstance(user, dict) or not isinstance(user.get('login'), str):
            raise DataError('GitHub public author identity missing')
        for key in ('created_at', 'updated_at'):
            if not isinstance(row.get(key), str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', row[key]):
                raise DataError('GitHub issue timestamp missing/invalid')
    return doc, rows


def protocol():
    return {
        'locked_at': utc(), 'workstream': 'WS-1 GitHub evidence scout',
        'source_domains': ['api.github.com', 'github.com'], 'anonymous_get_only': True,
        'max_retained_records': 15, 'max_response_records_requested': 15,
        'selection': 'first page, updated descending; keep API order; deduplicate by GitHub numeric issue ID; no replacement if duplicates',
        'query_plan': [{'label': label, 'query': query, 'per_page': size, 'sort': 'updated', 'order': 'desc', 'page': 1}
                       for label, query, size in SEARCHES],
        'limitations': ['Issue-search metadata/body are author allegations, not verified buyer/payment proof.',
                        'No cross-time trend evidence is created by a single search snapshot.',
                        'Anonymous REST issue search is used; authenticated GraphQL discussions and third-party attachments are not fetched.',
                        'No repository, external source, credential, private receipt or environment secret is read.']}


def collect(client, output, root=ROOT):
    output = Path(output)
    records, seen, failures, searches = [], set(), [], []
    for label, query, size in SEARCHES:
        url = 'https://api.github.com/search/issues?' + urlencode({'q': query, 'sort': 'updated', 'order': 'desc', 'per_page': size, 'page': 1})
        try:
            body, meta = client.get(url, label)
            doc, rows = parse_issues(body, size)
            searches.append({'label': label, 'url': url, 'total_count': doc['total_count'],
                             'response_count': len(rows), 'sha256': meta['sha256'], 'retrieved_at': meta['retrieved_at']})
            body_path = client.root / meta['body_file']
            for index, row in enumerate(rows):
                if row['id'] in seen:
                    continue
                seen.add(row['id'])
                source_body = row.get('body') or ''
                records.append({
                    'evidence_id': f'GH{len(records)+1:02d}', 'workstream': 'WS-1',
                    'source': 'github_issue', 'source_id': str(row['id']), 'url': row['html_url'],
                    'title': row['title'], 'author_public_handle': row['user']['login'],
                    'excerpt': source_body[:2400], 'excerpt_truncated': len(source_body) > 2400,
                    'created_at': row['created_at'], 'updated_at': row['updated_at'],
                    'retrieved_at': meta['retrieved_at'], 'comments_at_retrieval': row['comments'],
                    'query_label': label, 'query': query, 'query_url': url,
                    'source_request_url': url,
                    'raw_response': str(body_path.relative_to(root)).replace('\\', '/'),
                    'raw_response_path': str(body_path.relative_to(root)).replace('\\', '/'),
                    'raw_response_sha256': meta['sha256'],
                    'response_body': str(body_path.relative_to(root)).replace('\\', '/'),
                    'response_sha256': meta['sha256'], 'raw_locator': f'items[{index}]',
                    'field_locators': {'source_id': f'items[{index}].id', 'url': f'items[{index}].html_url',
                                       'title': f'items[{index}].title', 'excerpt': f'items[{index}].body',
                                       'author_public_handle': f'items[{index}].user.login',
                                       'comments_at_retrieval': f'items[{index}].comments'},
                    'evidence_level': 'SOURCE_ALLEGATION_OR_SELF_REPORT_UNVERIFIED',
                    'buyer_evidence': {'present': False, 'proof_type': None, 'url': None},
                    'payment_evidence': {'present': False, 'proof_type': None, 'url': None},
                    'trend_evidence': {'present': False, 'cohort': None, 't0': None, 't_plus': None, 'metric': None},
                    'assessment_limits': ['Public author handle is not a verified buyer identity.',
                                          'Body/price/paid-plan allegations do not establish authenticated payment proof.',
                                          'Single current snapshot; no same-cohort T+7/T+14 observation.'],
                })
            client.log('validation_pass', adapter='github_issues', query=label, records=len(rows), retained=len(records))
        except (DataError, UnicodeError, KeyError, TypeError, ValueError) as exc:
            failures.append({'label': label, 'url': url, 'error': str(exc)})
            client.log('validation_fail', adapter='github_issues', query=label, error=str(exc))
            # A query failure is an explicit GAP. No alternative source is fabricated.
        write_json(client.root / 'workstream_checkpoint.json', {'state': 'query_processed', 'query': label,
                   'retained': len(records), 'failed_queries': len(failures)})
    if len(records) > 15:
        raise DataError('WS-1 quota exceeded')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as stream:
        for record in records:
            stream.write((json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
    summary = {'finished_at': utc(), 'status': 'RESEARCH_DRAFT_ONLY', 'raw_count': len(records),
               'qualified_opportunities': 0, 'searches': searches, 'query_failures': failures,
               'gaps': ['No verified buyer identity/product/payment linkage.',
                        'No authenticated receipt/invoice/contract/public filing verified.',
                        'No longitudinal same-cohort repeated measurement.',
                        'Discussions were not fetched because this implementation uses public anonymous REST issue search.'],
               'output': str(output.relative_to(root)).replace('\\', '/'),
               'output_sha256': hashlib.sha256(output.read_bytes()).hexdigest()}
    write_json(client.root / 'workstream_summary.json', summary)
    write_json(client.root / 'workstream_checkpoint.json', {'state': 'stopped', 'status': summary['status'], 'retained': len(records)})
    client.log('workstream_stopped', retained=len(records), failures=len(failures), status=summary['status'])
    return summary


def main():
    from .live_shared import LiveClient
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts/live-evidence-v1/github_evidence.jsonl')
    args = parser.parse_args()
    work = ROOT / 'artifacts/live-evidence-v1/ws1'
    work.mkdir(parents=True, exist_ok=False)
    write_json(work / 'query_protocol.json', protocol())
    client = LiveClient(work, allowed_hosts=('api.github.com', 'github.com'), timeout=15,
                        attempts=2, interval=7, max_requests=12, deadline_seconds=300)
    print(json.dumps(collect(client, ROOT / args.output), ensure_ascii=True))


if __name__ == '__main__':
    main()
