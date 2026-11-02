"""One bounded anonymous HN Algolia scout. Public content is DATA only."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .core import DataError, strict_json, utc, write_json

QUERIES = [
    ('AI agent cost', 3),
    ('Claude Code pricing', 3),
    ('Codex pricing', 3),
    ('access denied agent', 2),
    ('rate limit agent', 2),
    ('incident agent', 2),
]


def freeze_protocol(anchor):
    if anchor.tzinfo is None:
        raise ValueError('timezone-aware anchor required')
    cutoff = anchor - timedelta(days=30)
    queries = []
    for index, (query, cap) in enumerate(QUERIES, 1):
        params = {'query': query, 'tags': '(story,comment)', 'hitsPerPage': cap,
                  'page': 0, 'numericFilters': f'created_at_i>={int(cutoff.timestamp())},created_at_i<={int(anchor.timestamp())}'}
        queries.append({'label': f'hn_query_{index}', 'query': query, 'cap': cap,
                        'url': 'https://hn.algolia.com/api/v1/search_by_date?' + urlencode(params)})
    return {'schema_version': 1, 'status': 'FROZEN_BEFORE_NETWORK',
            'source': 'hn.algolia.com', 'anchor_utc': anchor.isoformat(), 'cutoff_utc': cutoff.isoformat(),
            'max_returned_hits_total': 15, 'max_unique_retained': 15, 'minimum_target': 10,
            'selection': 'fixed query order; page 0, newest first; no backfill; deduplicate first observed objectID',
            'request_limit': 12, 'attempts_per_query': 2,
            'limitations': ['Selection is a bounded purposive sample, not an exhaustive market survey.',
                            'Public posts and payment allegations are unverified leads, not payment proof.'],
            'queries': queries}


def parse_response(body, query, protocol):
    doc = strict_json(body)
    if not isinstance(doc, dict) or not isinstance(doc.get('hits'), list):
        raise DataError('HN response missing hits array')
    if type(doc.get('nbHits')) is not int or doc['nbHits'] < 0:
        raise DataError('HN response missing/invalid total hit count')
    rows = doc['hits']
    if doc.get('query') != query['query'] or type(doc.get('page')) is not int or doc['page'] != 0:
        raise DataError('HN response query/page mismatch')
    if type(doc.get('hitsPerPage')) is not int or doc['hitsPerPage'] != query['cap']:
        raise DataError('HN response page cap mismatch')
    if len(rows) > query['cap'] or doc['nbHits'] < len(rows) or (not rows and doc['nbHits'] > 0):
        raise DataError('HN result count inconsistent')
    low = datetime.fromisoformat(protocol['cutoff_utc']).timestamp()
    high = datetime.fromisoformat(protocol['anchor_utc']).timestamp()
    normalized = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise DataError('HN hit must be object')
        ident = row.get('objectID')
        if not isinstance(ident, str) or not re.fullmatch('[0-9]+', ident):
            raise DataError('HN identity must be ASCII digits')
        created_i = row.get('created_at_i')
        if type(created_i) is not int or not low <= created_i <= high:
            raise DataError('HN hit outside frozen 30-day window')
        created = row.get('created_at')
        try:
            created_time = datetime.fromisoformat(created.replace('Z', '+00:00'))
            if created_time.tzinfo is None or abs(created_time.timestamp() - created_i) > 1:
                raise ValueError('date mismatch')
        except (ValueError, TypeError, AttributeError) as exc:
            raise DataError('HN created timestamp invalid') from exc
        tags = row.get('_tags')
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise DataError('HN tags invalid')
        if 'comment' in tags:
            kind, content_field = 'comment', 'comment_text'
            title = row.get('story_title') or row.get('title') or f'Comment {ident}'
        elif 'story' in tags:
            kind, content_field = 'story', 'story_text'
            title = row.get('title')
        else:
            raise DataError('HN hit type not recognized')
        if not isinstance(title, str) or not title.strip():
            raise DataError('HN title unavailable')
        content = row.get(content_field)
        if content is None:
            content = ''
        if not isinstance(content, str):
            raise DataError('HN body must be text or null')
        author = row.get('author')
        if not isinstance(author, str) or not author:
            raise DataError('HN author missing')
        metrics = {}
        for name in ('points', 'num_comments'):
            value = row.get(name)
            if value is not None:
                if type(value) is not int or value < 0:
                    raise DataError('HN metric invalid: ' + name)
                metrics[name] = value
        story_id = row.get('story_id')
        if story_id is not None and type(story_id) is not int:
            raise DataError('HN parent story_id invalid')
        source_url = row.get('url')
        if source_url is not None and not isinstance(source_url, str):
            raise DataError('HN source URL invalid')
        normalized.append({'source': 'hn', 'source_id': ident, 'kind': kind,
            'url': 'https://news.ycombinator.com/item?id=' + ident,
            'url_provenance': 'derived canonical URL from response objectID; not fetched',
            'source_url_from_response': source_url, 'external_urls_are_data_only': True,
            'title': title, 'author': author, 'story_id': story_id,
            'created_at': created, 'created_at_i': created_i, 'updated_at': row.get('updated_at'),
            'content_field': content_field, 'content_excerpt': content[:1600],
            'content_excerpt_policy': 'exact prefix of raw field; HTML is retained as untrusted text',
            'metrics': metrics, 'raw_locator': f'hits[{index}]',
            'field_locators': {name: f'hits[{index}].{name}' for name in
                               ('objectID', 'author', 'created_at', 'created_at_i', content_field, *metrics)},
            'query': query['query'], 'post_verification': 'UNVERIFIED_PUBLIC_POST',
            'buyer_evidence': {'present': False, 'proof_type': None, 'url': None},
            'payment_evidence': {'present': False, 'proof_type': None, 'url': None},
            'trend_evidence': {'present': False, 'cohort': None, 't0': None, 't_plus': None, 'metric': None},
            'gaps': ['Public author/post identity is not independently verified buyer identity.',
                     'No verified receipt/invoice/contract/public filing linked to buyer/product/time.',
                     'One retrieval is provisional T0 only; no comparable T+7/T+14.']})
    return normalized


def run(output=Path('artifacts/live-evidence-v1'), resume_dns=False):
    # Shared transport is supplied by the parent; import only at actual run time.
    from .live_shared import LiveClient
    output = Path(output)
    work = output / 'ws2'
    recovered_errors = []
    prior_requests = 0
    if resume_dns:
        prior = strict_json((work / 'manifest.json').read_text(encoding='utf-8'))
        existing = output / 'hn_evidence.jsonl'
        if (prior['retained_items'] != 0 or prior['returned_hits'] != 0 or existing.read_bytes()
                or not prior['errors'] or any('getaddrinfo' not in e['error'] for e in prior['errors'])
                or (work / 'initial_sandbox_manifest.json').exists()):
            raise DataError('resume permitted once only after zero-data sandbox DNS failure')
        protocol = strict_json((work / 'protocol.json').read_text(encoding='utf-8'))
        recovered_errors = prior['errors']
        write_json(work / 'initial_sandbox_manifest.json', prior)
        (work / 'initial_empty_evidence.jsonl').write_bytes(existing.read_bytes())
        prior_requests = sum(strict_json(s)['event'] == 'request_start'
                             for s in (work / 'requests/requests.jsonl').read_text(encoding='utf-8').splitlines())
    else:
        work.mkdir(parents=True, exist_ok=False)
        protocol = freeze_protocol(datetime.now(timezone.utc))
        write_json(work / 'protocol.json', protocol)
    protocol_sha = hashlib.sha256((work / 'protocol.json').read_bytes()).hexdigest()
    client = LiveClient(work / 'requests', allowed_hosts=('hn.algolia.com',), timeout=15,
                        attempts=2, interval=2, max_requests=12-prior_requests, deadline_seconds=300)
    if resume_dns:
        client.log('resume_same_frozen_protocol_after_sandbox_dns', prior_request_count=prior_requests,
                   protocol_sha256=protocol_sha)
    items, seen, errors, duplicate_ids = [], set(), [], []
    returned = 0
    for query in protocol['queries']:
        try:
            body, meta = client.get(query['url'], query['label'])
            parsed = parse_response(body, query, protocol)
            returned += len(parsed)
            for item in parsed:
                if item['source_id'] in seen:
                    duplicate_ids.append(item['source_id'])
                    continue
                seen.add(item['source_id'])
                item.update(evidence_id=f'HN{len(items)+1:02d}',
                    source_request_url=meta['url'], retrieved_at=meta['retrieved_at'],
                    raw_response_path=str(work / 'requests' / meta['body_file']).replace('\\', '/'),
                    raw_response_sha256=meta['sha256'], protocol_sha256=protocol_sha)
                items.append(item)
            client.log('validation_pass', source='hn', query=query['query'], returned_count=len(parsed), retained_count=len(items))
        except (DataError, ValueError, TypeError, KeyError) as exc:
            errors.append({'query': query['query'], 'error': str(exc)})
            client.log('validation_fail', source='hn', query=query['query'], error=str(exc))
            break
        write_json(work / 'checkpoint.json', {'state': 'query_validated', 'query': query['query'],
                                               'returned_count': returned, 'retained_count': len(items)})
    assert returned <= 15 and len(items) <= 15
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'hn_evidence.jsonl'
    if path.exists() and not resume_dns:
        raise DataError('refusing to overwrite HN evidence')
    path.write_bytes((''.join(json.dumps(item, ensure_ascii=True, allow_nan=False) + '\n' for item in items)).encode())
    manifest = {'run_kind': 'single_live_workstream', 'source': 'hn.algolia.com',
                'status': 'RESEARCH_DRAFT_ONLY', 'protocol_sha256': protocol_sha,
                'finished_at': utc(), 'returned_hits': returned, 'retained_items': len(items),
                'duplicate_ids': duplicate_ids, 'errors': errors,
                'recovered_initial_transport_errors': recovered_errors,
                'target_met': len(items) >= 10, 'claims': 0, 'opportunities': [],
                'gaps': [] if len(items) >= 10 else ['SCOUT_TARGET_NOT_MET: bounded queries returned fewer than 10 unique items'],
                'output_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    write_json(work / 'manifest.json', manifest)
    write_json(work / 'checkpoint.json', {'state': 'stopped', 'status': 'RESEARCH_DRAFT_ONLY', 'retained_count': len(items)})
    print(json.dumps({'retained': len(items), 'returned': returned, 'errors': errors}))
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='artifacts/live-evidence-v1')
    parser.add_argument('--resume-dns', action='store_true')
    args = parser.parse_args()
    run(Path(args.output), resume_dns=args.resume_dns)


if __name__ == '__main__':
    main()
