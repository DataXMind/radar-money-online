"""Offline provenance audit, discovery scoring and merge of the frozen HN v4 scan.

Only captured source statements are evaluated here. No network, product fetch,
checkout, identity verification or revenue inference is performed.
"""
import csv
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .core import DataError, strict_json, write_json
from .evidence_tiers import evaluate_candidate
from .live_shared import public_url
from .live_v4_hn import OUT, ROOT, baseline_audit, freeze_protocol, parse_response, public_product_url
from .payment_infra_v4 import evaluate_infrastructure

CLAIM_LIMIT = 8


def _load(path):
    if path.stat().st_size > 4_000_000:
        raise DataError('CRITICAL: input exceeds byte limit')
    return strict_json(path.read_text(encoding='utf-8'))


def _jsonl(path):
    if path.stat().st_size > 4_000_000:
        raise DataError('CRITICAL: JSONL exceeds byte limit')
    return [strict_json(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _checked_response(root, relative, digest, url, folder):
    path = (root / relative).resolve()
    if not path.is_relative_to((root / OUT / folder).resolve()) or path.suffix != '.body':
        raise DataError('CRITICAL: raw response path outside approved capture directory')
    if path.stat().st_size > 4_000_000 or _sha(path) != digest:
        raise DataError('CRITICAL: raw response hash mismatch')
    meta = _load(path.with_suffix('.meta.json'))
    public_url(url, {'hn.algolia.com'})
    if (meta.get('status') != 200 or meta.get('error_response') is not False
            or meta.get('url') != url or meta.get('sha256') != digest
            or meta.get('bytes') != path.stat().st_size or meta.get('body_file') != path.name):
        raise DataError('CRITICAL: HTTP response metadata mismatch')
    return path, meta


def checked_records(root=ROOT):
    """Verify immutable capture and derive corrected URLs from the same raw bytes.

    Initial hn_evidence.jsonl is preserved. Its former post_text_urls extraction
    included abbreviated anchor labels; this single field is rederived offline.
    All other parser-derived fields must still exactly match the captured row.
    """
    root = Path(root).resolve()
    out = root / OUT
    protocol_path = out / 'scan/protocol.json'
    protocol, manifest = _load(protocol_path), _load(out / 'scan/manifest.json')
    expected_protocol = freeze_protocol(datetime.fromisoformat(protocol['anchor_utc']),
        datetime.fromisoformat(protocol['budget_started_utc']))
    digest = _sha(protocol_path)
    if protocol != expected_protocol or manifest.get('protocol_sha256') != digest:
        raise DataError('CRITICAL: frozen protocol differs from approved scope/hash')
    records = _jsonl(out / 'hn_evidence.jsonl')
    if len(records) > 30 or len({r.get('evidence_id') for r in records}) != len(records):
        raise DataError('CRITICAL: duplicate evidence identity or record cap exceeded')
    parsed_by_url, replayed, seen = {}, [], set()
    for search in manifest['searches']:
        query = next((q for q in protocol['queries'] if q['url'] == search['source_url']), None)
        if query is None or query['url'] in parsed_by_url:
            raise DataError('CRITICAL: response outside frozen query set or repeated search')
        relative = OUT / 'scan/requests' / search['body_file']
        path, meta = _checked_response(root, relative, search['raw_response_sha256'], query['url'], 'scan/requests')
        rows = parse_response(path.read_text(encoding='utf-8'), query, protocol)
        if len(rows) != search['returned']:
            raise DataError('CRITICAL: search count differs from raw')
        parsed_by_url[query['url']] = (rows, path, meta)
        for row in rows:
            if row['source_id'] not in seen:
                seen.add(row['source_id'])
                replayed.append(row['source_id'])
    if [r.get('source_id') for r in records] != replayed:
        raise DataError('CRITICAL: retained identities differ from frozen deduplicated sample')
    result = []
    for item in records:
        if item.get('protocol_sha256') != digest:
            raise DataError('CRITICAL: record protocol hash mismatch')
        match = re.fullmatch(r'hits\[(\d+)\]', item.get('raw_locator', ''))
        if not match or item.get('source_request_url') not in parsed_by_url:
            raise DataError('CRITICAL: raw row locator missing or outside captured query')
        rows, path, meta = parsed_by_url[item['source_request_url']]
        try:
            expected = rows[int(match[1])]
        except IndexError as exc:
            raise DataError('CRITICAL: raw row locator outside response') from exc
        if (item.get('raw_response_path') != path.relative_to(root).as_posix()
                or item.get('raw_response_sha256') != meta['sha256']
                or item.get('retrieved_at') != meta['retrieved_at']
                or any(item.get(k) != v for k, v in expected.items() if k != 'post_text_urls')):
            raise DataError('CRITICAL: normalized record differs from exact raw row')
        result.append({**item, 'post_text_urls': expected['post_text_urls']})
    if len(result) != manifest['unique_retained'] or sum(s['returned'] for s in manifest['searches']) != manifest['returned_hits']:
        raise DataError('CRITICAL: capture manifest counts mismatch')
    return result


def _quote(record, quote):
    if not isinstance(quote, str) or not quote or quote not in record['story_text']:
        raise DataError('CRITICAL: reviewed quote is absent from same raw post text')
    return quote


def _trace(record, quote, field='story_text'):
    return {'evidence_id': record['evidence_id'], 'source_url': record['source_request_url'],
        'raw_response_path': record['raw_response_path'], 'raw_response_sha256': record['raw_response_sha256'],
        'raw_locator': record['raw_locator'] + '.' + field, 'quote': quote,
        'review_status': 'CONFIRMED_SOURCE_STATEMENT'}


def score_lead(record, review):
    """Discovery score only; pending pricing and provider mentions are not tiers."""
    if review.get('evidence_id') != record.get('evidence_id'):
        raise DataError('CRITICAL: review bound to another evidence identity')
    product, founder = review.get('product'), review.get('founder')
    quote = _quote(record, review.get('context_quote'))
    if (not isinstance(product, str) or not product.strip()
            or product.casefold() not in record['title'].casefold()
            or not isinstance(founder, str) or record['author'].casefold() not in founder.casefold()
            or review.get('product_url') not in record['post_text_urls']
            or not public_product_url(review['product_url'])):
        raise DataError('CRITICAL: product/founder/post-text URL review linkage mismatch')
    homepage = review.get('homepage_url')
    if homepage is not None and (not public_product_url(homepage)
            or homepage not in [record.get('source_url_from_response'), *record['post_text_urls']]):
        raise DataError('CRITICAL: proposed homepage URL was not observed in this source row')
    mentions = re.findall(r'\b(?:Stripe|Paddle|Lemon\s?Squeezy)\b', record['story_text'], re.I)
    price_quote = review.get('pricing_quote')
    pricing = 0
    if price_quote is not None:
        _quote(record, price_quote)
        # Caller reviews product/price meaning; discount-only values cannot pass.
        if (not re.search(r'(?:\b(?:USD|EUR|GBP|VND)\b\s*\$?|[$€£])\s*\d+(?:[.,]\d+)?', price_quote)
                or re.search(r'\b(?:discount|off the|off final|save up to|placeholder|TODO)\b', price_quote, re.I)):
            raise DataError('CRITICAL: pricing review lacks a concrete actual product price')
        pricing = 30
    score = {'integration': 30 if mentions else 0, 'pricing': pricing, 'linkage': 40}
    return {**review, 'post_url': record['url'], 'author_handle': record['author'],
        'provider_mentions': list(dict.fromkeys(m.lower().replace(' ', '') for m in mentions)),
        'payment_provider_mention': ', '.join(mentions) or None, 'score_components': score,
        'score': sum(score.values()), 'pricing_verification': 'POST_PRICE_ONLY_PAGE_PENDING' if pricing else 'PENDING_VERIFICATION',
        'homepage_verification': 'PENDING_EXACT_URL_APPROVAL', 'pricing_page_verified': False,
        'integration_verified': False, 'checkout_executed': False, 'founder_identity_verified': False,
        'source_statement_review_only': True, 'provenance': _trace(record, quote)}


def apply_opportunity_gate(candidates, eligible, other_gates_pass=True):
    """Minimum sample/score gate cannot be bypassed by one qualified product."""
    passed = len(candidates) >= 5 and sum(c['score'] >= 70 for c in candidates) >= 5
    return eligible[:5] if passed and other_gates_pass else []


def _select_claims(candidates, claims):
    """Preserve all reviews while publishing the inherited eight-claim maximum."""
    scores = {candidate['evidence_id']: candidate['score'] for candidate in candidates}
    selected = sorted(claims, key=lambda claim: (-scores[claim['evidence_id']], claim['evidence_id']))[:CLAIM_LIMIT]
    return [{**claim, 'claim_id': f'V4-C{index:02d}'} for index, claim in enumerate(selected, 1)]


def _g1(root):
    prior = _load(root / OUT / 'retry-preflight-20261103/preflight_results.json')
    passing = next((p for p in prior['results'] if p.get('status') == 200), None)
    if prior.get('g1') != 'PASS' or passing is None:
        raise DataError('CRITICAL: G1 HTTP200 evidence missing')
    relative = OUT / 'retry-preflight-20261103/hn' / passing['body_file']
    _checked_response(root, relative, passing['sha256'], passing['url'], 'retry-preflight-20261103/hn')
    return {'status': 'PASS', 'http_status': 200, 'source_url': passing['url'],
        'raw_response_path': relative.as_posix(), 'raw_response_sha256': passing['sha256'],
        'accepted_by_user_before_scan': True}


def build_ledger(root=ROOT, now=None):
    root = Path(root).resolve()
    out = root / OUT
    records = checked_records(root)
    manifest, protocol = _load(out / 'scan/manifest.json'), _load(out / 'scan/protocol.json')
    review = _load(out / 'component_review.json')
    if not review.get('reviewer') or not review.get('reviewed_at'):
        raise DataError('CRITICAL: reviewer/time missing')
    by_id = {r['evidence_id']: r for r in records}
    leads = review['leads']
    if len({r['evidence_id'] for r in leads}) != len(leads):
        raise DataError('CRITICAL: duplicate candidate reviews')
    candidates, claims = [], []
    for lead in leads:
        if lead['evidence_id'] not in by_id:
            raise DataError('CRITICAL: review refers to uncaptured record')
        record = by_id[lead['evidence_id']]
        candidate = score_lead(record, lead)
        metadata = {**_trace(record, record['title'], 'title'), 'kind': 'post_metadata'}
        tier = evaluate_candidate({'product': lead['product'], 'founder': lead['founder'],
            'points': [], 'metadata': [metadata]}, allowed_hosts={'hn.algolia.com'})
        # No integration/page capture is supplied by a discovery post review.
        # Do not convert a discovery score or a price quote into those proofs.
        infrastructure = evaluate_infrastructure({'product': lead['product'], 'founder': lead['founder']}, approved_urls=())
        candidate.update(tier=tier['tier'], verdict=tier['verdict'], eligible=False,
            tier_evaluation=tier, infrastructure_evaluation=infrastructure)
        candidates.append(candidate)
        claims.append({'claim_id': f'V4-C{len(claims)+1:02d}', **candidate['provenance'],
            'product': lead['product'], 'kind': 'OBSERVED_SOURCE_STATEMENT', 'verdict': 'HYPED',
            'statement': 'The captured Show HN post contains this source-attributed maker statement; product reachability, integration, payment and revenue are unverified.'})
    claims = _select_claims(candidates, claims)
    excluded = review.get('excluded_url_posts', [])
    covered = {r['evidence_id'] for r in leads} | {r['evidence_id'] for r in excluded}
    if covered != {r['evidence_id'] for r in records if r['post_text_urls']}:
        raise DataError('CRITICAL: review does not account for every post containing public URLs')
    for row in excluded:
        if not row.get('reason') or row['evidence_id'] not in by_id:
            raise DataError('CRITICAL: excluded source review missing')
    events = _jsonl(out / 'scan/requests/requests.jsonl')
    starts = sum(e['event'] == 'request_start' for e in events)
    responses = [e for e in events if e['event'] == 'data_ingress']
    errors = [e for e in events if e['event'] == 'request_error']
    http_errors = sum(type(e.get('status')) is int and 400 <= e['status'] <= 599 for e in errors)
    if starts != manifest['http_attempts'] or http_errors != manifest['http_4xx_5xx']:
        raise DataError('CRITICAL: request journal differs from manifest')
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise DataError('timezone-aware review time required')
    started = datetime.fromisoformat(protocol['budget_started_utc'])
    elapsed = (current - started).total_seconds()
    guard = protocol['wall_clock_seconds'] * protocol['g4_time_guard_fraction']
    shortlist = [c for c in candidates if c['score'] >= 70]
    enough = len(candidates) >= 5 and len(shortlist) >= 5
    g4_stop = elapsed > guard and not enough
    g2_pass = http_errors / max(starts, 1) <= .30
    gates = {'G1': _g1(root),
        'G2': {'status': 'PASS' if g2_pass else 'FAIL', 'http_4xx_5xx': http_errors,
            'requests': starts, 'error_rate': http_errors / max(starts, 1)},
        'G3': {'status': 'PASS' if enough else 'FAIL', 'candidate_count': len(candidates),
            'candidates_at_least_70': len(shortlist), 'minimum_each': 5},
        'G4': {'status': 'ACQUISITION_STOP' if g4_stop else 'WITHIN_TIME_GUARD',
            'elapsed_wall_clock_seconds': elapsed, 'guard_seconds': guard,
            'capture_finished_elapsed_seconds': (datetime.fromisoformat(manifest['finished_at']) - started).total_seconds(),
            'includes_long_user_usage_limit_pause': True, 'budget_reset_recorded': False,
            'token_consumption': None, 'model_usd_consumption': None,
            'paid_http_api_calls': 0, 'additional_acquisition_permitted': not g4_stop},
        'G5': {'status': 'SOURCE_PROVENANCE_PASS_PRODUCT_PAGES_PENDING',
            'public_source_records': len(records), 'verified_product_pages': 0,
            'verified_pricing_pages': 0, 'approved_product_urls': []}}
    opportunities = apply_opportunity_gate(candidates, [], g2_pass and not g4_stop)
    originals = _jsonl(out / 'hn_evidence.jsonl')
    corrected = [r['evidence_id'] for r, old in zip(records, originals) if r['post_text_urls'] != old['post_text_urls']]
    return {'run_id': 'live-evidence-v4', 'status': 'RESEARCH_DRAFT_ONLY',
        'evaluated_at': current.isoformat(), 'reviewed_at': review['reviewed_at'], 'reviewer': review['reviewer'],
        'raw_count': len(records), 'returned_hits': manifest['returned_hits'], 'claim_count': len(claims),
        'claim_selection': {'limit': CLAIM_LIMIT, 'available_reviewed_candidates': len(candidates),
            'rule': 'descending discovery score, then stable evidence_id; retain every candidate review',
            'selected_evidence_ids': [claim['evidence_id'] for claim in claims]},
        'candidate_count': len(candidates), 'shortlist_count': len(shortlist), 'opportunity_count': len(opportunities),
        'source_counts': {'hn': len(records), 'github': 0},
        'request_counts': {'scan_attempts': starts, 'scan_http_200': sum(e.get('status') == 200 for e in responses),
            'scan_http_4xx_5xx': http_errors, 'scan_dns_errors': sum('getaddrinfo' in e.get('error', '') for e in errors)},
        'raw_items': records, 'claims': claims, 'candidates': candidates, 'shortlist': shortlist,
        'excluded_url_posts': excluded, 'opportunities': opportunities, 'gates': gates,
        'baseline': baseline_audit(root), 'approved_product_urls': [], 'product_urls_fetched': [],
        'normalization_notes': {'method': 'offline reparse of original raw bytes; only href plus non-anchor text URLs',
            'corrected_records': corrected, 'initial_normalized_jsonl_preserved': True, 'new_network_requests': 0},
        'gaps': ['FEWER_THAN_FIVE_CANDIDATES_AT_LEAST_70', 'NO_PROVIDER_MENTION_IN_CAPTURED_POSTS',
            'NO_VERIFIED_CURRENT_PRODUCT_INTEGRATION', 'PRICING_PAGES_PENDING_EXACT_URL_APPROVAL',
            'NO_VERIFIED_PAYMENT_OR_THREE_POINT_REVENUE_HISTORY', 'T7_T14_NOT_OBSERVED',
            *(['G4_WALL_CLOCK_GUARD_REACHED_AFTER_PAUSE'] if g4_stop else [])]}


def save(root=ROOT, now=None):
    root = Path(root).resolve()
    out = root / OUT
    ledger = build_ledger(root, now=now)
    write_json(out / 'evidence_ledger.json', ledger)
    write_json(out / 'candidates.json', {'candidates': ledger['candidates'], 'shortlist': ledger['shortlist'],
        'excluded_url_posts': ledger['excluded_url_posts']})
    with (out / 'opportunities.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['rank', 'product', 'tier', 'verdict', 'score', 'evidence_id'])
        writer.writeheader()
        writer.writerows(ledger['opportunities'])
    summary = {k: ledger[k] for k in ('run_id', 'status', 'evaluated_at', 'raw_count', 'returned_hits',
        'claim_count', 'claim_selection', 'candidate_count', 'shortlist_count', 'opportunity_count', 'request_counts', 'gates', 'normalization_notes', 'gaps')}
    write_json(out / 'merge_summary.json', summary)
    return summary


if __name__ == '__main__':
    import json
    print(json.dumps(save(), ensure_ascii=False))
