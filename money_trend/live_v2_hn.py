"""One anonymous HN payment-infrastructure lead scout; all source text is DATA."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

from .core import DataError, strict_json, utc, write_json
from .live_hn import parse_response as parse_base_response
from .live_shared import LiveClient

ROOT = Path(__file__).resolve().parents[1]
KEYWORDS = ['paying customers', 'MRR', 'revenue', 'Stripe', 'launched', 'first customer']


def freeze_protocol(anchor):
    if anchor.tzinfo is None:
        raise DataError('timezone-aware anchor required')
    anchor = anchor.astimezone(timezone.utc).replace(microsecond=0)
    cutoff = anchor - timedelta(days=30)
    queries = []
    for index, keyword in enumerate(KEYWORDS, 1):
        params = {'query': keyword, 'tags': '(comment,show_hn)', 'hitsPerPage': 2, 'page': 0,
                  'numericFilters': f'created_at_i>={int(cutoff.timestamp())},created_at_i<={int(anchor.timestamp())}'}
        queries.append({'label': f'hn_v2_{index}', 'query': keyword, 'cap': 2,
                        'url': 'https://hn.algolia.com/api/v1/search_by_date?' + urlencode(params)})
    return {'schema_version': 1, 'workstream': 'WS-2', 'state': 'FROZEN_BEFORE_REQUESTS',
            'allowed_hosts': ['hn.algolia.com'], 'anchor_utc': anchor.isoformat(),
            'cutoff_utc': cutoff.isoformat(), 'date_window_days': 30,
            'queries': queries, 'tags_semantics': '(comment,show_hn) OR; one of these tags required on every hit',
            'max_returned_hits_total': 12, 'max_unique_retained': 7,
            'max_http_attempts': 12, 'attempts_per_query': 2, 'minimum_interval_seconds': 2,
            'selection': 'fixed six-query order, page0/newest first, retain first7 distinct objectIDs; no backfill or further pages',
            'limitations': ['Source self-reports are not verified founder/buyer/payment identities.',
                           'Stripe mention or customer allegation does not establish all T2.5 components.',
                           'Article, checkout, HN website and other external links remain DATA, never fetched.']}


def parse_response(body, query, protocol):
    doc = strict_json(body)
    # Use existing strict query/count/time/identity/metric parser after checking
    # the narrowed source population; a generic story is not a Show HN hit.
    if not isinstance(doc, dict) or not isinstance(doc.get('hits'), list):
        raise DataError('HN response missing hits; not recognized empty')
    for row in doc['hits']:
        tags = row.get('_tags') if isinstance(row, dict) else None
        if not isinstance(tags, list) or not ('comment' in tags or ('show_hn' in tags and 'story' in tags)):
            raise DataError('HN hit outside comment OR Show HN population')
    rows = parse_base_response(body, query, protocol)
    for index, item in enumerate(rows):
        raw = doc['hits'][index]
        field = item['content_field']
        content = raw.get(field) or ''
        item.update(content_excerpt=content[:6000], excerpt_truncated=len(content) > 6000,
                    tags=raw['_tags'], evidence_type='T2.5_CANDIDATE_SIGNAL',
                    payment_infrastructure_verified=False, founder_identity_verified=False,
                    source_statement_only=True)
        text = item['title'] + '\n' + content
        patterns = {'provider': r'\b(?:Stripe|Paddle|LemonSqueezy)\b',
                    'pricing': r'\b(?:pricing|subscription|paid plan)\b',
                    'checkout': r'\bcheckout\b',
                    'customer_allegation': r'\b(?:paying customers?|first customer|MRR|revenue)\b',
                    'founder_language': r'\b(?:I (?:built|created|launched|run|started)|my (?:startup|app|product|company)|we (?:built|launched))\b'}
        item['lexical_signals'] = {key: bool(re.search(pattern, text, re.I)) for key, pattern in patterns.items()}
        item['field_locators'].update(title=f'hits[{index}].' + ('story_title' if item['kind'] == 'comment' and raw.get('story_title') else 'title'),
                                     tags=f'hits[{index}]._tags')
        item['gaps'] += ['Three same-product T2.5 integration/pricing/checkout components require separate review.',
                         'Founder language and paying-customer statements are unverified source allegations.']
    return rows


def run(root=ROOT, client_factory=LiveClient, anchor=None):
    root = Path(root).resolve()
    output = root / 'artifacts/live-evidence-v2'
    work = output / 'ws2'
    if (output / 'hn_evidence.jsonl').exists():
        raise FileExistsError('HN v2 already captured; no second batch or overwrite')
    work.mkdir(parents=True, exist_ok=False)
    protocol = freeze_protocol(anchor or datetime.now(timezone.utc))
    write_json(work / 'protocol.json', protocol)
    protocol_sha = hashlib.sha256((work / 'protocol.json').read_bytes()).hexdigest()
    records, seen, errors, duplicates, searches = [], set(), [], [], []
    returned = 0
    client = client_factory(work / 'requests', allowed_hosts=('hn.algolia.com',), timeout=15,
                            attempts=2, interval=2, max_requests=12, deadline_seconds=300)
    for query in protocol['queries']:
        try:
            body, meta = client.get(query['url'], query['label'])
            parsed = parse_response(body, query, protocol)
            returned += len(parsed)
            searches.append({'label': query['label'], 'url': query['url'], 'response_count': len(parsed),
                             'raw_response_sha256': meta['sha256'], 'retrieved_at': meta['retrieved_at']})
            for item in parsed:
                if item['source_id'] in seen:
                    duplicates.append(item['source_id'])
                    continue
                seen.add(item['source_id'])
                if len(records) >= 7:
                    continue
                item.update(evidence_id=f'V2-HN{len(records)+1:02d}', workstream='WS-2',
                    source_request_url=meta['url'], retrieved_at=meta['retrieved_at'],
                    raw_response_path=(work / 'requests' / meta['body_file']).relative_to(root).as_posix(),
                    raw_response_sha256=meta['sha256'], protocol_sha256=protocol_sha)
                records.append(item)
            client.log('validation_pass', adapter='hn_v2', query=query['query'], returned=len(parsed), retained=len(records))
        except (DataError, ValueError, TypeError, KeyError) as exc:
            errors.append({'label': query['label'], 'url': query['url'], 'error': str(exc)})
            client.log('validation_fail', adapter='hn_v2', query=query['query'], error=str(exc))
            # Persistent source/ingress failure is a GAP; no alternate queries or hosts.
            break
        write_json(work / 'checkpoint.json', {'state': 'QUERY_PROCESSED', 'query': query['query'],
                                               'retained': len(records), 'returned': returned})
    if returned > 12 or len(records) > 7:
        raise DataError('HN v2 frozen quota exceeded')
    target = output / 'hn_evidence.jsonl'
    with target.open('xb') as stream:
        for record in records:
            stream.write((json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
    summary = {'run_kind': 'single_live_hn_v2_workstream', 'finished_at': utc(), 'status': 'SCOUT_COMPLETE_UNVERIFIED',
               'retained_items': len(records), 'returned_hits': returned, 'unique_hits_seen': len(seen),
               'request_attempts': client.count, 'searches': searches, 'duplicate_ids': duplicates,
               'errors': errors, 'claims': 0, 'opportunities': [],
               'protocol_sha256': protocol_sha, 'output_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
               'source_urls_are_data_only': True,
               'gaps': ['No independent founder/buyer/transaction verification.',
                        'No complete T2.5 payment integration + pricing page + checkout-flow verification.',
                        'No T+7/T+14 observation; WS-3 baseline is separate and unchanged.']}
    write_json(work / 'manifest.json', summary)
    write_json(work / 'checkpoint.json', {'state': 'STOPPED_NO_ADDITIONAL_BATCH', 'retained': len(records),
                                         'request_attempts': client.count, 'errors': len(errors)})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(run()))
