"""Untrusted public data ingestion. No source content is executed or prompted."""
import hashlib
import json
import math
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

MAX_BYTES = 4_000_000
MAX_RAW = 15
MAX_CLAIMS = 8
MAX_OPPORTUNITIES = 5


class DataError(ValueError):
    pass


def utc():
    return datetime.now(timezone.utc).isoformat()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DataError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise DataError('non-finite JSON number: ' + value)
    try:
        result = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, RecursionError) as exc:
        raise DataError('invalid JSON: ' + str(exc)) from exc
    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise DataError('non-finite JSON number')
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        if isinstance(value, list):
            for child in value:
                finite(child)
    try:
        finite(result)
    except RecursionError as exc:
        raise DataError('JSON nesting too deep') from exc
    return result


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)


class Scripts(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.active = False
        self.buffer = []
        self.documents = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            attrs = dict(attrs)
            self.active = attrs.get('type', '').lower() == 'application/json'
            self.buffer = []

    def handle_data(self, data):
        if self.active:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.documents.append(''.join(self.buffer))
            self.active = False


def github_rows(body):
    """Return recognized rows, including [], or raise on unknown/malformed schema."""
    body = body.lstrip('\ufeff \r\n\t')
    if body.startswith(('{', '[')):
        docs = [strict_json(body)]
    else:
        parser = Scripts()
        parser.feed(body)
        docs = [strict_json(doc) for doc in parser.documents]
    for doc in docs:
        if not isinstance(doc, dict) or not isinstance(doc.get('payload'), dict):
            continue
        payload = doc['payload']
        if 'blackbirdSearchRoute' in payload:
            route = payload['blackbirdSearchRoute']
            if not isinstance(route, dict):
                raise DataError('invalid blackbirdSearchRoute')
            if 'results' not in route:
                raise DataError('missing blackbird results')
            rows = route['results']
        elif 'results' in payload:
            rows = payload['results']
        else:
            continue
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise DataError('GitHub results must be object array')
        return rows
    raise DataError('unrecognized GitHub response; not an empty result')


def parse_github(body, limit=8):
    rows = github_rows(body)
    items = []
    seen = set()
    for row in rows:
        repo = row.get('repo', {}).get('repository', {}) if isinstance(row.get('repo'), dict) else {}
        name = repo.get('name') if isinstance(repo, dict) else None
        owner = repo.get('owner_login') if isinstance(repo, dict) else None
        full = row.get('hl_name') or row.get('name')
        if owner and name:
            if not isinstance(owner, str) or not isinstance(name, str):
                raise DataError('invalid GitHub owner/name type')
            full = owner + '/' + name
        if not isinstance(full, str):
            raise DataError('GitHub repo identity missing')
        # Only strip known highlighting markup; never evaluate HTML or scripts.
        full = re.sub(r'</?em>', '', full)
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', full):
            raise DataError('invalid GitHub repository identity')
        if full.lower() in seen:
            continue
        seen.add(full.lower())
        desc = row.get('hl_trunc_description') or row.get('description') or ''
        if not isinstance(desc, str):
            raise DataError('invalid GitHub description')
        items.append({'source': 'github', 'source_id': full, 'url': 'https://github.com/' + full,
                      'title': full, 'text': desc[:2000]})
    return items[:limit]


def parse_hn(body, limit=7):
    doc = strict_json(body)
    if not isinstance(doc, dict) or not isinstance(doc.get('hits'), list):
        raise DataError('HN hits array missing')
    items = []
    seen = set()
    for row in doc['hits']:
        if not isinstance(row, dict):
            raise DataError('HN hit must be object')
        ident, title = row.get('objectID'), row.get('title')
        if not isinstance(ident, str) or not ident.isdigit() or not isinstance(title, str) or not title.strip():
            raise DataError('invalid HN identity/title')
        for field in ('points', 'num_comments'):
            value = row.get(field)
            if type(value) is not int or value < 0:
                raise DataError('invalid HN ' + field)
        if ident in seen:
            continue
        seen.add(ident)
        items.append({'source': 'hn', 'source_id': ident, 'url': 'https://news.ycombinator.com/item?id=' + ident,
                      'title': title[:500], 'text': '', 'points': row['points'], 'comments': row['num_comments']})
    return items[:limit]


class Client:
    """Public GET only, domain allowlist, no credentials, bounded timeout/retries."""
    def __init__(self, root, timeout=15, attempts=3, interval=2, sleeper=time.sleep):
        if not 0 < timeout <= 30 or not 1 <= attempts <= 3 or not 0 <= interval <= 10:
            raise ValueError('invalid network bounds')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.timeout, self.attempts, self.interval = timeout, attempts, interval
        self.sleep = sleeper
        self.last = None
        self.sequence = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), SafeRedirect())

    def log(self, event, **fields):
        with (self.root / 'requests.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'time': utc(), 'event': event, **fields}, allow_nan=False) + '\n')

    def get(self, url, label):
        validate_url(url)
        if not re.fullmatch(r'[a-z0-9_-]+', label):
            raise ValueError('unsafe request label')
        for attempt in range(1, self.attempts + 1):
            if self.last is not None:
                self.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            self.sequence += 1
            stem = f'{uuid.uuid4().hex[:12]}_{self.sequence:03d}_{label}_{attempt}'
            self.log('request_start', url=url, attempt=attempt, request_id=stem)
            write_json(self.root / 'checkpoint.json', {'state': 'request_started', 'url': url, 'attempt': attempt, 'request_id': stem})
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'AI-Money-Trend-Local-MVP/0.1', 'Accept': 'text/html,application/json'})
                started = time.monotonic()
                with self.opener.open(request, timeout=self.timeout) as response:
                    status = response.status
                    chunks = []
                    size = 0
                    while True:
                        if time.monotonic() - started > self.timeout:
                            raise TimeoutError('response deadline exceeded')
                        chunk = response.read(min(65536, MAX_BYTES + 1 - size))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        size += len(chunk)
                        if size > MAX_BYTES:
                            self.log('data_ingress_rejected', url=url, bytes_read=size, reason='byte_limit', request_id=stem)
                            raise DataError('response exceeds byte limit')
                    raw = b''.join(chunks)
                    content_type = response.headers.get('Content-Type', '')
                digest = hashlib.sha256(raw).hexdigest()
                raw_path = self.root / (stem + '.body')
                raw_path.write_bytes(raw)
                meta = {'url': url, 'status': status, 'retrieved_at': utc(), 'sha256': digest,
                        'bytes': len(raw), 'content_type': content_type, 'body_file': raw_path.name}
                write_json(self.root / (stem + '.meta.json'), meta)
                self.log('data_ingress', **meta, request_id=stem)
                write_json(self.root / 'checkpoint.json', {'state': 'response_saved', **meta})
                try:
                    body = raw.decode('utf-8', errors='strict')
                except UnicodeDecodeError as exc:
                    raise DataError('response is not UTF-8') from exc
                return body, meta
            except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, DataError) as exc:
                status = getattr(exc, 'code', None)
                self.log('request_error', url=url, attempt=attempt, error=str(exc), status=status, request_id=stem)
                write_json(self.root / 'checkpoint.json', {'state': 'request_failed', 'url': url, 'attempt': attempt, 'error': str(exc)})
                retryable = not isinstance(exc, DataError) and (status is None or status in (429, 500, 502, 503, 504))
                if not retryable or attempt == self.attempts:
                    raise DataError(f'request failed: {url}: {exc}') from exc
                retry_after = exc.headers.get('Retry-After') if isinstance(exc, urllib.error.HTTPError) else None
                delay = min(8, 2 ** attempt)
                if retry_after is not None:
                    # Do not retry early when server asks for a long/date-based cooldown.
                    if not retry_after.isdigit() or int(retry_after) > 8:
                        raise DataError('rate-limit cooldown exceeds local retry budget') from exc
                    delay = max(delay, int(retry_after))
                self.log('retry_wait', seconds=delay, url=url)
                self.sleep(delay)


def validate_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('github.com', 'hn.algolia.com') or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise DataError('only credential-free HTTPS GitHub/HN public requests allowed')


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        # Refuse even allowlisted redirects: no hidden/unlogged/unthrottled requests.
        raise DataError('redirect refused; use the canonical public endpoint')
