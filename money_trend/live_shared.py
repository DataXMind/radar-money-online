"""Scoped anonymous public GET for the explicitly authorized live evidence run."""
import hashlib
import http.client
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .core import DataError, MAX_BYTES, utc, write_json

ALLOWED = frozenset(('api.github.com', 'github.com', 'hn.algolia.com'))
APPROVED_EXPLICIT_HOSTS = ALLOWED | frozenset(('feed.indiehackers.world',))


def public_url(url, hosts=ALLOWED):
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment
                or any(k.lower() in ('access_token', 'token', 'api_key', 'key') for k, _ in urllib.parse.parse_qsl(parsed.query))):
            raise DataError('only scoped credential-free HTTPS public URLs allowed')
    except ValueError as exc:
        raise DataError('invalid public URL') from exc


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise DataError('redirect refused; no additional domain/request followed')


class LiveClient:
    def __init__(self, root, allowed_hosts=ALLOWED, timeout=15, attempts=2, interval=2,
                 max_requests=12, deadline_seconds=300, sleeper=time.sleep, accept='application/json'):
        if (not set(allowed_hosts) or not set(allowed_hosts) <= APPROVED_EXPLICIT_HOSTS or not 0 < timeout <= 20
                or type(attempts) is not int or not 1 <= attempts <= 2 or not 2 <= interval <= 10
                or type(max_requests) is not int or not 1 <= max_requests <= 12 or not 0 < deadline_seconds <= 300):
            raise ValueError('invalid live network budget')
        if accept not in ('application/json', 'application/rss+xml, application/atom+xml, application/xml, text/xml, text/html'):
            raise ValueError('unsupported accept header')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.hosts, self.timeout, self.attempts = frozenset(allowed_hosts), timeout, attempts
        self.interval, self.max_requests, self.deadline = interval, max_requests, time.monotonic() + deadline_seconds
        self.sleep, self.last, self.count = sleeper, None, 0
        self.accept = accept
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def log(self, event, **fields):
        with (self.root / 'requests.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
            import json
            stream.write(json.dumps({'time': utc(), 'event': event, **fields}, allow_nan=False) + '\n')

    def save(self, raw, url, status, headers, stem, error_response=False):
        body_path = self.root / (stem + '.body')
        body_path.write_bytes(raw)
        meta = {'url': url, 'status': status, 'retrieved_at': utc(), 'sha256': hashlib.sha256(raw).hexdigest(),
                'bytes': len(raw), 'body_file': body_path.name, 'content_type': headers.get('Content-Type', ''),
                'error_response': error_response,
                'rate_limit': {key: headers.get(key) for key in ('X-RateLimit-Remaining', 'X-RateLimit-Reset', 'Retry-After') if headers.get(key) is not None}}
        write_json(self.root / (stem + '.meta.json'), meta)
        self.log('data_ingress', request_id=stem, **meta)
        write_json(self.root / 'checkpoint.json', {'state': 'response_saved', **meta})
        return meta

    def get(self, url, label):
        public_url(url, self.hosts)
        if not re.fullmatch('[a-z0-9_-]{1,80}', label):
            raise DataError('unsafe request label')
        for attempt in range(1, self.attempts + 1):
            delay = max(0, self.interval - (time.monotonic() - self.last)) if self.last is not None else 0
            if self.count >= self.max_requests or time.monotonic() + delay >= self.deadline:
                self.log('budget_stop', url=url, requests=self.count)
                raise DataError('live request/time budget exhausted')
            if delay:
                self.sleep(delay)
            self.last = time.monotonic()
            self.count += 1
            stem = f'{self.count:03d}_{label}_{attempt}_{uuid.uuid4().hex[:8]}'
            self.log('request_start', url=url, attempt=attempt, request_id=stem)
            write_json(self.root / 'checkpoint.json', {'state': 'request_started', 'url': url, 'attempt': attempt})
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'AI-Money-Trend-Evidence/1.0', 'Accept': self.accept})
                started = time.monotonic()
                with self.opener.open(request, timeout=min(self.timeout, max(0.1, self.deadline - started))) as response:
                    raw = bytearray()
                    while True:
                        if time.monotonic() - started >= self.timeout or time.monotonic() >= self.deadline:
                            raise TimeoutError('response deadline exceeded')
                        chunk = response.read(min(65536, MAX_BYTES + 1 - len(raw)))
                        if not chunk:
                            break
                        raw.extend(chunk)
                        if len(raw) > MAX_BYTES:
                            self.log('data_ingress_rejected', url=url, bytes_read=len(raw), reason='byte_limit')
                            raise DataError('response exceeds byte limit')
                    if response.status != 200:
                        raise DataError('unexpected successful HTTP status')
                    meta = self.save(bytes(raw), url, response.status, response.headers, stem)
                try:
                    return bytes(raw).decode('utf-8'), meta
                except UnicodeError as exc:
                    raise DataError('response is not UTF-8') from exc
            except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException, DataError) as exc:
                status = getattr(exc, 'code', None)
                if isinstance(exc, urllib.error.HTTPError):
                    try:
                        self.save(exc.read(16_384), url, status, exc.headers, stem, error_response=True)
                    except (OSError, http.client.HTTPException) as capture_error:
                        self.log('error_body_capture_failed', error=type(capture_error).__name__, url=url)
                    finally:
                        exc.close()
                self.log('request_error', url=url, request_id=stem, attempt=attempt, status=status, error=str(exc))
                write_json(self.root / 'checkpoint.json', {'state': 'request_failed', 'url': url, 'attempt': attempt, 'error': str(exc)})
                retryable = not isinstance(exc, DataError) and (status is None or status in (429, 500, 502, 503, 504))
                if not retryable or attempt == self.attempts:
                    raise DataError(f'public request failed: {url}: {exc}') from exc
                retry_after = exc.headers.get('Retry-After') if isinstance(exc, urllib.error.HTTPError) else None
                cooldown = min(8, 2 ** attempt)
                if retry_after is not None:
                    if not retry_after.isdigit() or int(retry_after) > 8:
                        raise DataError('server cooldown exceeds bounded retry budget') from exc
                    cooldown = max(cooldown, int(retry_after))
                if time.monotonic() + cooldown >= self.deadline:
                    raise DataError('retry would exceed deadline') from exc
                self.log('retry_wait', url=url, seconds=cooldown)
                self.sleep(cooldown)
