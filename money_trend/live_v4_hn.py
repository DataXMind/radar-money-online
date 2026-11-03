"""Bounded HN Show HN capture; outbound links are DATA and never fetched."""
import argparse
import hashlib
import ipaddress
import json
import re
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .core import DataError, strict_json, utc, write_json
from .live_hn import parse_response as parse_base_response
from .live_shared import LiveClient

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('artifacts/live-evidence-v4')
KEYWORDS = ('AI agent', 'AI tool', 'launched')
NON_PRODUCT_HOSTS = frozenset(('github.com', 'api.github.com', 'news.ycombinator.com',
    'hn.algolia.com', 'reddit.com', 'producthunt.com', 'theresanaiforthat.com',
    'feed.indiehackers.world', 'youtube.com', 'youtu.be', 'x.com', 'twitter.com'))


def public_product_url(value):
    """Syntactic public URL screen only: never resolves or fetches a hostname."""
    if not isinstance(value, str) or any(ord(c) < 33 for c in value):
        return False
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower().rstrip('.')
        if (p.scheme not in ('https', 'http') or not host or '.' not in host
                or p.username or p.password or p.port not in (None, 80, 443)
                or host in NON_PRODUCT_HOSTS or any(host.endswith('.' + h) for h in NON_PRODUCT_HOSTS)
                or host.endswith(('.local', '.internal', '.localhost'))):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return not re.fullmatch(r'[0-9.]+', host)
    except ValueError:
        return False


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []
        self.non_anchor_text = []
        self.anchor_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            self.urls.extend(v for k, v in attrs if k.lower() == 'href' and v)
            self.anchor_depth += 1

    def handle_endtag(self, tag):
        if tag.lower() == 'a':
            self.anchor_depth = max(0, self.anchor_depth - 1)

    def handle_data(self, data):
        if not self.anchor_depth:
            self.non_anchor_text.append(data)


def text_urls(text):
    parser = Links()
    parser.feed(text)
    plain = re.findall(r'https?://[^\s<>"\']+', ' '.join(parser.non_anchor_text))
    # HN abbreviates anchor labels; only href is authoritative inside anchors.
    raw = parser.urls + [u.rstrip('.,;)') for u in plain if not u.endswith(('...', '\u2026'))]
    return list(dict.fromkeys(u for u in raw if public_product_url(u)))


def freeze_protocol(anchor, budget_started):
    if anchor.tzinfo is None or budget_started.tzinfo is None:
        raise DataError('timezone-aware timestamps required')
    anchor = anchor.astimezone(timezone.utc).replace(microsecond=0)
    cutoff = anchor - timedelta(days=30)
    queries = []
    for i, word in enumerate(KEYWORDS, 1):
        params = {'query': word, 'tags': 'show_hn', 'hitsPerPage': 10, 'page': 0,
                  'numericFilters': f'created_at_i>={int(cutoff.timestamp())},created_at_i<={int(anchor.timestamp())}'}
        queries.append({'label': f'hn_v4_{i}', 'query': word, 'cap': 10,
            'url': 'https://hn.algolia.com/api/v1/search_by_date?' + urlencode(params)})
    return {'schema_version': 1, 'run_id': 'live-evidence-v4', 'state': 'FROZEN_BEFORE_SCAN',
        'anchor_utc': anchor.isoformat(), 'cutoff_utc': cutoff.isoformat(), 'window_days': 30,
        'queries': queries, 'allowed_hosts': ['hn.algolia.com'], 'max_returned_hits_total': 30,
        'max_unique_retained': 30, 'target_returned_hits': [20, 30],
        'selection': 'three fixed queries, newest first, page0, ten hits each; first objectID wins; no backfill',
        'product_url_rule': 'public product homepage/demo URL must occur in story_text; top-level url alone is insufficient',
        'max_http_attempts': 6, 'dns_retries_per_query': 1, 'dns_retry_delay_seconds': 60,
        'g1': 'accepted prior HTTP200 captured in retry-preflight-20261103',
        'g2': 'stop if HTTP4xx/5xx requests / all scan attempts >0.30; DNS is not HTTP4xx/5xx',
        'g3': 'at least5 product candidates AND at least5 scoring>=70; else no opportunities',
        'budget_started_utc': budget_started.isoformat(), 'wall_clock_seconds': 1800,
        'g4_time_guard_fraction': 0.70, 'token_budget': 150000, 'api_usd_budget': 3,
        'unobservable_budgets': ['session model token and USD consumption are unavailable to this script'],
        'g5': 'public source URL with HTTP200 raw provenance; product reachability pending exact URL approval',
        'approved_product_urls': [], 'follow_outbound_links': False}


def parse_response(body, query, protocol):
    doc = strict_json(body)
    if not isinstance(doc, dict) or not isinstance(doc.get('hits'), list):
        raise DataError('CRITICAL: HN schema missing hits')
    for row in doc['hits']:
        tags = row.get('_tags') if isinstance(row, dict) else None
        if not isinstance(tags, list) or 'show_hn' not in tags or 'story' not in tags or 'comment' in tags:
            raise DataError('CRITICAL: non-Show-HN story returned')
    rows = parse_base_response(body, query, protocol)
    for i, item in enumerate(rows):
        text = doc['hits'][i].get('story_text') or ''
        item.update(story_text=text, content_excerpt=text[:6000],
            content_excerpt_policy='exact prefix; full story_text retained separately',
            tags=doc['hits'][i]['_tags'], post_text_urls=text_urls(text),
            product_urls_fetched=False, founder_identity_verified=False,
            evidence_type='SHOW_HN_DISCOVERY_RECORD', tier='T3', verdict='HYPED')
    return rows


def baseline_audit(root):
    prior = strict_json((root / 'artifacts/live-evidence-v2/ws3/audit.json').read_text(encoding='utf-8'))
    for name, digest in prior['historical_files_sha256'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root / 'artifacts') or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise DataError('CRITICAL: historical baseline hash changed')
    rows = [strict_json(s) for s in (root / prior['snapshot']).read_text(encoding='utf-8').splitlines() if s]
    if len(rows) != 15:
        raise DataError('CRITICAL: historical baseline count changed')
    return {'integrity': 'PASS', 'baseline_records': 15, 'historical_files_sha256': prior['historical_files_sha256'],
        'snapshot_sha256': prior['snapshot_sha256'], 't7_executed': False, 'new_observations': 0,
        'baseline_excluded_from_discovery_merge': True, 'audited_at': utc()}


def run(root=ROOT, anchor=None, budget_started=None, client_factory=LiveClient, sleeper=time.sleep):
    root = Path(root).resolve()
    out = root / OUT
    work = out / 'scan'
    # No overwrite or second batch; prior preflight artifacts remain untouched.
    if work.exists():
        raise DataError('scan directory already exists; no implicit rescan')
    audit = baseline_audit(root)
    prior = strict_json((out / 'retry-preflight-20261103/preflight_results.json').read_text(encoding='utf-8'))
    if prior.get('g1') != 'PASS' or not any(x.get('status') == 200 for x in prior['results']):
        raise DataError('G1 has not passed')
    work.mkdir(parents=True)
    protocol = freeze_protocol(anchor or datetime.now(timezone.utc), budget_started or datetime.now(timezone.utc))
    write_json(work / 'protocol.json', protocol)
    write_json(work / 'baseline_audit.json', audit)
    protocol_sha = hashlib.sha256((work / 'protocol.json').read_bytes()).hexdigest()
    client = client_factory(work / 'requests', allowed_hosts={'hn.algolia.com'}, attempts=1,
        max_requests=6, timeout=15, interval=2, deadline_seconds=300)
    records, seen, errors, duplicates, searches = [], set(), [], [], []
    returned, http_errors, stopped = 0, 0, None
    started = datetime.fromisoformat(protocol['budget_started_utc'])
    for query in protocol['queries']:
        for attempt in (1, 2):
            if (datetime.now(timezone.utc) - started).total_seconds() > 1260:
                stopped = 'G4_TIME_BUDGET_STOP'
                break
            try:
                body, meta = client.get(query['url'], query['label'] + f'_try{attempt}')
            except DataError as exc:
                events = [strict_json(s) for s in (work / 'requests/requests.jsonl').read_text().splitlines()]
                last = next((e for e in reversed(events) if e['event'] == 'request_error'), {})
                status = last.get('status')
                http_errors += int(type(status) is int and 400 <= status <= 599)
                errors.append({'query': query['query'], 'attempt': attempt, 'status': status, 'error': str(exc)})
                if http_errors / max(client.count, 1) > .30:
                    stopped = 'G2_HTTP_ERROR_RATE_STOP'
                    break
                if 'getaddrinfo' in str(exc).lower() and attempt == 1:
                    client.log('dns_retry_wait', seconds=60, query=query['query'])
                    print(json.dumps({'state': 'DNS_RETRY_WAIT', 'seconds': 60, 'query': query['query']}), flush=True)
                    sleeper(60)
                    continue
                break  # Failed workstream; move only to another already-frozen HN query.
            parsed = parse_response(body, query, protocol)
            returned += len(parsed)
            searches.append({'query': query['query'], 'returned': len(parsed), 'source_url': meta['url'],
                'raw_response_sha256': meta['sha256'], 'body_file': meta['body_file']})
            for item in parsed:
                if item['source_id'] in seen:
                    duplicates.append(item['source_id'])
                    continue
                seen.add(item['source_id'])
                item.update(evidence_id=f'V4-HN{len(records)+1:02d}',
                    source_request_url=meta['url'], retrieved_at=meta['retrieved_at'],
                    raw_response_path=(work / 'requests' / meta['body_file']).relative_to(root).as_posix(),
                    raw_response_sha256=meta['sha256'], protocol_sha256=protocol_sha)
                records.append(item)
            print(json.dumps({'query': query['query'], 'returned': len(parsed), 'unique_retained': len(records)}), flush=True)
            break
        if stopped:
            break
    with (out / 'hn_evidence.jsonl').open('xb') as stream:
        for item in records:
            stream.write((json.dumps(item, ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8'))
    write_json(work / 'baseline_audit_after.json', baseline_audit(root))
    summary = {'status': stopped or 'SCOUT_COMPLETE_UNVERIFIED', 'finished_at': utc(),
        'returned_hits': returned, 'unique_retained': len(records), 'duplicate_ids': duplicates,
        'with_post_text_public_urls': sum(bool(r['post_text_urls']) for r in records),
        'http_attempts': client.count, 'http_4xx_5xx': http_errors, 'errors': errors,
        'searches': searches, 'protocol_sha256': protocol_sha, 'opportunities': [],
        'product_urls_fetched': [], 'paid_api_calls': 0}
    write_json(work / 'manifest.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true', required=True)
    parser.add_argument('--budget-start', required=True)
    args = parser.parse_args()
    print(json.dumps(run(budget_started=datetime.fromisoformat(args.budget_start))))
