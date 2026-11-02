"""Offline audit/merge of an authorized RSS capture; never makes requests.

Only reviewed source statements may become T2. Raw ingress and economic records
have separate counts. A failed request is never an empty recognized RSS feed.
"""
import hashlib
import re
from pathlib import Path

from .core import DataError, strict_json
from .evidence_tiers import evaluate_candidate
from .indie_rss import FEED_HOST, parse_feed
from .live_shared import public_url

KEYWORDS = ['AI agent', 'Claude Code', 'Codex', 'AI automation', 'MRR report']
FIELDS = ('product', 'founder', 'metric', 'currency', 'cadence', 'value',
          'period_start', 'period_end', 'observed_at')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    if path.stat().st_size > 4_000_000:
        raise DataError('JSON exceeds byte budget')
    return strict_json(path.read_text(encoding='utf-8'))


def validate_source_config(config, root):
    source = config.get('sources', {}).get('indiehackers_rss', {})
    if (source.get('allowed_hosts') != [FEED_HOST] or source.get('keywords') != KEYWORDS
            or source.get('execution_mode') != 'EXPLICIT_HUMAN_APPROVAL_PER_RUN'
            or source.get('automatic_refresh') is not False
            or source.get('minimum_opportunity_tier') != 'T2'
            or config.get('limits') != {'raw_items': 15, 'claims': 8, 'opportunities': 5}):
        raise DataError('RSS scope/policy changed; review required')
    criteria = (root / config['criteria_file']).resolve()
    if not criteria.is_relative_to((root / 'docs').resolve()) or sha(criteria) != config.get('criteria_sha256'):
        raise DataError('criteria pin mismatch')


def audit_capture(root, out):
    """Verify every request/ingress and body before parsing any RSS content."""
    root, out = root.resolve(), out.resolve()
    if not out.is_relative_to(root / 'artifacts'):
        raise DataError('output must be under artifacts')
    protocol = load(out / 'execution_protocol.json')
    queries = protocol['queries']
    if protocol['source_host'] != FEED_HOST or [q['keyword'] for q in queries] != KEYWORDS:
        raise DataError('unrecognized frozen source protocol')
    urls = [q['url'] for q in queries]
    for url in [f'https://{FEED_HOST}/', *urls]:
        public_url(url, (FEED_HOST,))
    events = [strict_json(line) for line in (out / 'requests/requests.jsonl').read_text(encoding='utf-8').splitlines()]
    starts = [e for e in events if e.get('event') == 'request_start']
    ingress = [e for e in events if e.get('event') == 'data_ingress']
    if not starts or len(starts) > 12 or len({e['request_id'] for e in starts}) != len(starts):
        raise DataError('invalid request log or request budget')
    allowed_urls = {f'https://{FEED_HOST}/', *urls}
    if any(e.get('url') not in allowed_urls for e in starts):
        raise DataError('request outside frozen query plan')
    meta_paths = list((out / 'requests').glob('*.meta.json'))
    if len(meta_paths) != len(ingress):
        raise DataError('ingress metadata/log count mismatch')
    metas, entries, gaps, recognized_empty = [], [], [], []
    parsed_feeds = 0
    for path in meta_paths:
        meta = load(path)
        stem = path.name.removesuffix('.meta.json')
        if (meta.get('url') not in allowed_urls or type(meta.get('status')) is not int
                or not 200 <= meta['status'] <= 599 or meta.get('body_file') != stem + '.body'):
            raise DataError('invalid ingress metadata')
        body = path.with_name(meta['body_file'])
        if body.is_symlink() or not body.resolve().is_relative_to((out / 'requests').resolve()):
            raise DataError('raw response escapes capture directory')
        if sha(body) != meta.get('sha256') or body.stat().st_size != meta.get('bytes'):
            raise DataError('raw response hash/size mismatch')
        matching = [e for e in ingress if e.get('request_id') == stem]
        if len(matching) != 1 or any(matching[0].get(k) != v for k, v in meta.items()):
            raise DataError('metadata does not match logged ingress')
        if not any(e['request_id'] == stem and e['url'] == meta['url'] for e in starts):
            raise DataError('ingress has no matching request')
        metas.append({**meta, 'request_id': stem, 'raw_response_path': body.relative_to(root).as_posix(),
                      'meta_path': path.relative_to(root).as_posix()})
        if meta['status'] != 200 or meta.get('error_response') is not False:
            gaps.append('SOURCE_UNAVAILABLE_HTTP_' + str(meta['status']))
            continue
        if meta['url'] not in urls:
            continue  # Discovery HTML is not an economic source record.
        try:
            rows = parse_feed(body.read_bytes())
        except DataError:
            gaps.append('RSS_INGRESS_ERROR')
            continue
        parsed_feeds += 1
        if not rows:
            recognized_empty.append(meta['url'])
        for row in rows:
            entries.append({**row, 'source_url': meta['url'], 'raw_response_path': body.relative_to(root).as_posix(),
                            'raw_response_sha256': meta['sha256']})
    # Deduplicate cross-query syndication; conflict is a review GAP.
    records, seen = [], {}
    for entry in entries:
        key = entry['source_id']
        if key in seen:
            prior = seen[key]
            if any(prior[k] != entry[k] for k in ('content', 'author', 'title')):
                gaps.append('CONFLICTING_SYNDICATED_ENTRY')
            continue
        seen[key] = entry
        text = (entry['title'] + '\n' + entry['content']).casefold()
        if any(k.casefold() in text for k in KEYWORDS) and re.search(r'\bmrr\b|\brevenue\b', text):
            if len(records) < 15:
                records.append(entry)
    query_status = []
    for query in queries:
        matches = [m for m in metas if m['url'] == query['url']]
        state = ('NOT_RUN' if not matches else 'FAILED' if any(m['status'] != 200 for m in matches)
                 else 'RECOGNIZED_EMPTY' if query['url'] in recognized_empty else 'RESPONSE_SAVED')
        query_status.append({**query, 'state': state, 'attempts': len([e for e in starts if e['url'] == query['url']]),
                             'http_statuses': [m['status'] for m in sorted(matches, key=lambda m: m['retrieved_at'])]})
    discovery = (root / protocol['discovery_source']).resolve()
    if (not discovery.is_relative_to(out / 'requests') or sha(discovery) != protocol['discovery_sha256']):
        raise DataError('discovery hash mismatch')
    return {'request_attempts': len(starts), 'response_count': len(metas),
            'responses': sorted(metas, key=lambda m: m['retrieved_at']), 'records': records,
            'parsed_feed_responses': parsed_feeds, 'recognized_empty_urls': recognized_empty,
            'query_status': query_status, 'gaps': list(dict.fromkeys(gaps)),
            'source_status': 'SOURCE_UNAVAILABLE' if gaps else 'AVAILABLE'}


def evaluate_reviewed(candidates, records):
    """Require exact raw-entry mapping before the pure T2 policy is applied.

    field_quotes binds each normalized economic field to literal source text.
    A human still reviews normalization and founder/product identity; this
    confirms a statement's provenance, never the truth of self-reported revenue.
    Verified payment needs a separate document-verification workflow.
    """
    if not isinstance(candidates, list) or len(candidates) > 8:
        raise DataError('candidate/claim budget exceeded')
    evaluations, opportunities, claims = [], [], []
    used_ids, used_products = set(), set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise DataError('invalid reviewed candidate')
        points = candidate.get('points', [])
        if not isinstance(points, list):
            raise DataError('invalid revenue points')
        for point in points:
            if not isinstance(point, dict):
                raise DataError('invalid revenue point')
            matches = [r for r in records if all(point.get(k) == r.get(k) for k in
                       ('source_url', 'raw_response_path', 'raw_response_sha256', 'raw_locator'))]
            if len(matches) != 1:
                raise DataError('revenue point does not map to one retained raw entry')
            row = matches[0]
            if row['duplicate_conflicting_content']:
                raise DataError('conflicting duplicate requires review')
            text = '\n'.join([row['title'], row.get('author') or '', row['content']])
            if not isinstance(point.get('quote'), str) or not point['quote'] or point['quote'] not in text:
                raise DataError('revenue quote missing from raw entry')
            mappings = point.get('field_quotes', {})
            for field in FIELDS:
                mapping = mappings.get(field, {})
                if (not isinstance(mapping, dict) or mapping.get('value') != point.get(field)
                        or not isinstance(mapping.get('quote'), str) or not mapping['quote']
                        or mapping['quote'] not in text):
                    raise DataError('missing raw field mapping: ' + field)
            if point.get('evidence_id') in used_ids:
                raise DataError('duplicate reviewed economic observation ID')
            used_ids.add(point.get('evidence_id'))
        # RSS revenue reports cannot self-attest authenticity of transaction documents.
        if candidate.get('t1_proof') or candidate.get('metadata'):
            raise DataError('this RSS merger accepts reviewed revenue history only')
        evaluation = evaluate_candidate(candidate)
        identity = (candidate.get('product'), candidate.get('founder'))
        if identity in used_products:
            raise DataError('duplicate candidate entity')
        used_products.add(identity)
        evaluations.append({'product': candidate.get('product'), 'founder': candidate.get('founder'), **evaluation})
        claims.append({'claim_id': f'IH-C{len(claims) + 1:02d}', 'product': candidate.get('product'),
                       'founder': candidate.get('founder'), 'kind': 'SOURCE_ATTRIBUTED_REVENUE_HISTORY',
                       'points': points, 'evaluation': evaluation})
        if evaluation['eligible'] and len(opportunities) < 5:
            opportunities.append({'product': candidate['product'], 'founder': candidate['founder'], **evaluation,
                                  'buyer_evidence': {'present': False, 'proof_type': None, 'url': None},
                                  'payment_evidence': {'present': False, 'proof_type': None, 'url': None},
                                  'trend_evidence': {'present': False, 'cohort': None, 't0': None,
                                                     't_plus': None, 'metric': None},
                                  'revenue_history_evidence': {'present': True, 'points': points}})
    return {'claims': claims, 'evaluations': evaluations, 'opportunities': opportunities}
