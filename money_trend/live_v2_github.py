"""WS-1: bounded public repository/README scout; all source contents are DATA."""
import argparse
import base64
import binascii
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, urlencode

from .core import DataError, strict_json, utc, write_json
from .live_shared import LiveClient

ROOT = Path(__file__).resolve().parents[1]
QUERIES = [
    ('ai_agent', 'topic:ai-agent stripe pricing in:readme'),
    ('paddle', 'topic:paddle saas checkout in:readme'),
    ('lemonsqueezy', 'topic:lemonsqueezy subscription in:readme'),
    ('stripe_saas', 'topic:stripe topic:saas payment in:readme'),
]
NAME = re.compile(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+')


def parse_repositories(body, per_page=2):
    doc = strict_json(body)
    if (not isinstance(doc, dict) or type(doc.get('total_count')) is not int or doc['total_count'] < 0
            or doc.get('incomplete_results') is not False or not isinstance(doc.get('items'), list)
            or doc.get('errors') or doc.get('message')):
        raise DataError('unrecognized or incomplete repo search; not genuine empty')
    rows = doc['items']
    if len(rows) > per_page or doc['total_count'] < len(rows) or (not rows and doc['total_count']):
        raise DataError('repository search count mismatch')
    for row in rows:
        name = row.get('full_name') if isinstance(row, dict) else None
        if (not isinstance(name, str) or not NAME.fullmatch(name)
                or row.get('html_url') != 'https://github.com/' + name
                or row.get('url') != 'https://api.github.com/repos/' + name
                or type(row.get('id')) is not int or row['id'] < 1
                or not isinstance(row.get('topics'), list)
                or any(not isinstance(topic, str) for topic in row['topics'])):
            raise DataError('invalid repository identity/topics')
    return rows


def decode_readme(body):
    doc = strict_json(body)
    if (not isinstance(doc, dict) or doc.get('type') != 'file' or doc.get('encoding') != 'base64'
            or not isinstance(doc.get('content'), str) or type(doc.get('size')) is not int
            or not 0 <= doc['size'] <= 500_000 or not isinstance(doc.get('path'), str)
            or not re.fullmatch(r'[a-f0-9]{40,64}', doc.get('sha', ''))):
        raise DataError('unrecognized bounded README JSON')
    if not re.fullmatch(r'(?:[^/]+/)*README(?:\.[A-Za-z0-9]+)?', doc['path'], re.I):
        raise DataError('readme endpoint returned unexpected file path')
    try:
        raw = base64.b64decode(''.join(doc['content'].split()), validate=True)
        text = raw.decode('utf-8-sig')
    except (binascii.Error, UnicodeError) as exc:
        raise DataError('invalid UTF-8/base64 README') from exc
    if len(raw) != doc['size']:
        raise DataError('decoded README size mismatch')
    return doc, text


def signals(text):
    patterns = {'payment_provider': r'\b(?:stripe|paddle|lemon\s?squeezy|lemonsqueezy)\b',
                'pricing': r'\bpricing\b', 'checkout': r'\bcheckout\b'}
    result = {}
    lines = text.splitlines()
    for kind, pattern in patterns.items():
        found = []
        for index, line in enumerate(lines, 1):
            if re.search(pattern, line, re.I) and len(found) < 3:
                found.append({'quote': line[:1400], 'decoded_readme_line': index,
                              'quote_truncated': len(line) > 1400})
        result[kind] = {'mentioned': bool(found), 'quotes': found,
                        'verification': 'SOURCE_MENTION_ONLY_NOT_ACTIVE_INFRASTRUCTURE'}
    return result


def protocol():
    return {'recorded_at': utc(), 'workstream': 'WS-1 GitHub T2.5 scout',
            'allowed_hosts': ['api.github.com'], 'public_anonymous_get_only': True,
            'queries': [{'label': label, 'q': q, 'url': 'https://api.github.com/search/repositories?' + urlencode(
                {'q': q, 'sort': 'updated', 'order': 'desc', 'per_page': 2, 'page': 1})} for label, q in QUERIES],
            'selection': 'Fixed first-page order; dedupe numeric repository ID across searches; max8 unique repos. No replacement queries.',
            'detail_selection': 'Read /readme for discovered repositories in retained order; README only, no file tree or secret/config paths.',
            'max_retained_repos': 8, 'max_discovery_http_attempts': 4, 'max_readme_http_attempts': 8,
            'max_http_attempts_total': 12, 'attempts_per_url': 1, 'interval_seconds': 7,
            'timeout_seconds': 15, 'stop': 'Any request/schema failure stops this source; never bypass a rate limit.',
            'limitations': ['README mentions and repository topics are leads, not evidence that a checkout is active.',
                            'No payment/pricing external domain or source code is executed/fetched.',
                            'No paid customer/payment transaction is proved; a single snapshot does not prove trend.']}


def run(root=ROOT, client_factory=LiveClient):
    root = Path(root).resolve()
    out = root / 'artifacts/live-evidence-v2'
    work = out / 'ws1'
    work.mkdir(parents=True, exist_ok=False)
    plan = protocol()
    write_json(work / 'protocol.json', plan)
    client = client_factory(work / 'requests', allowed_hosts=('api.github.com',), timeout=15,
                            attempts=1, interval=7, max_requests=12, deadline_seconds=300)
    records, seen, searches, errors = [], set(), [], []
    try:
        for query in plan['queries']:
            body, meta = client.get(query['url'], query['label'])
            rows = parse_repositories(body)
            client.log('validation_pass', adapter='v2_repository_search', records=len(rows), url=query['url'])
            searches.append({'url': query['url'], 'returned': len(rows), 'raw_sha256': meta['sha256']})
            for index, row in enumerate(rows):
                if row['id'] in seen:
                    continue
                seen.add(row['id'])
                records.append({'evidence_id': f'V2-GH{len(records)+1:02d}', 'source': 'github_repository',
                    'source_id': str(row['id']), 'repo': row['full_name'], 'url': row['html_url'],
                    'title': row.get('description') or row['full_name'], 'topics': row['topics'],
                    'source_request_url': meta['url'], 'retrieved_at': meta['retrieved_at'],
                    'raw_response_path': (client.root / meta['body_file']).relative_to(root).as_posix(),
                    'raw_response_sha256': meta['sha256'], 'raw_locator': f'items[{index}]',
                    'readme': None, 'evidence_type': 'T2.5_SIGNAL_UNVERIFIED',
                    'verified_payment': False, 'active_payment_infrastructure_verified': False,
                    'gaps': ['CHECKOUT_RUNTIME_NOT_OBSERVED', 'NO_VERIFIED_BUYER_OR_TRANSACTION', 'T7_T14_NOT_OBSERVED']})
            write_json(work / 'checkpoint.json', {'state': 'discovery_validated', 'request_attempts': client.count, 'retained': len(records)})
        for index, item in enumerate(records):
            url = 'https://api.github.com/repos/' + quote(item['repo'], safe='/') + '/readme'
            body, meta = client.get(url, f'readme_{index + 1}')
            doc, text = decode_readme(body)
            expected_api = 'https://api.github.com/repos/' + item['repo'] + '/contents/' + quote(doc['path'], safe='/')
            if doc.get('url', '').split('?', 1)[0] != expected_api:
                raise DataError('README response belongs to unexpected repository/file')
            item['readme'] = {'source_request_url': meta['url'], 'retrieved_at': meta['retrieved_at'],
                'raw_response_path': (client.root / meta['body_file']).relative_to(root).as_posix(),
                'raw_response_sha256': meta['sha256'], 'raw_locator': 'content (strict base64 decoded UTF-8)',
                'path': doc['path'], 'blob_sha': doc['sha'], 'decoded_sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                'excerpt': text[:3000], 'excerpt_truncated': len(text) > 3000,
                'component_signals': signals(text),
                'scaffold_or_starter_mention': bool(re.search(r'\bstarter\b|\bboilerplate\b|\btemplate\b', text, re.I))}
            item['all_three_components_mentioned'] = all(v['mentioned'] for v in item['readme']['component_signals'].values())
            if item['all_three_components_mentioned']:
                item['gaps'].append('THREE_MENTIONS_DO_NOT_VERIFY_DEPLOYED_ACTIVE_CHECKOUT')
            if item['readme']['scaffold_or_starter_mention']:
                item['gaps'].append('POSSIBLE_STARTER_OR_BOILERPLATE_NOT_DEPLOYED_PRODUCT')
            client.log('validation_pass', adapter='v2_readme', repo=item['repo'], decoded_bytes=doc['size'], source_only=True)
            write_json(work / 'checkpoint.json', {'state': 'readme_validated', 'repo': item['repo'], 'request_attempts': client.count})
    except (DataError, ValueError, TypeError, KeyError) as exc:
        errors.append({'error': str(exc), 'request_attempts': client.count})
        client.log('source_stopped', reason=str(exc), request_attempts=client.count)
    finally:
        path = out / 'github_evidence.jsonl'
        with path.open('xb') as stream:
            for record in records:
                stream.write((json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
        summary = {'state': 'STOPPED', 'finished_at': utc(), 'request_attempts': client.count,
                   'retained_repos': len(records), 'readmes_captured': sum(r['readme'] is not None for r in records),
                   'searches': searches, 'errors': errors, 'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                   'status': 'RESEARCH_DRAFT_ONLY_PENDING_REVIEW', 'opportunities': []}
        write_json(work / 'workstream_summary.json', summary)
        write_json(work / 'checkpoint.json', {'state': 'STOPPED', 'request_attempts': client.count, 'retained': len(records), 'errors': errors})
    return summary


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    result = run()
    print(json.dumps(result, ensure_ascii=False))
