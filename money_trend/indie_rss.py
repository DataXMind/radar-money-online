"""Bounded RSS/Atom parsing; source markup and URLs remain untrusted DATA.

raw_locator uses a documented zero-based entry position, not one-based XPath.
This module has no network client and never fetches entry links or XML entities.
"""
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from .core import DataError

MAX_FEED_BYTES = 4_000_000
MAX_DEPTH = 64
MAX_NODES = 20_000
FEED_HOST = 'feed.indiehackers.world'
ATOM = 'http://www.w3.org/2005/Atom'
CONTENT = 'http://purl.org/rss/1.0/modules/content/'
DC = 'http://purl.org/dc/elements/1.1/'


def _text_input(body):
    if isinstance(body, bytes):
        if len(body) > MAX_FEED_BYTES:
            raise DataError('feed exceeds byte budget')
        try:
            return body.decode('utf-8-sig')
        except UnicodeError as exc:
            raise DataError('feed is not UTF-8') from exc
    if not isinstance(body, str):
        raise DataError('feed body must be bytes or text')
    if len(body.encode('utf-8')) > MAX_FEED_BYTES:
        raise DataError('feed exceeds byte budget')
    return body.lstrip('\ufeff')


def _xml(body):
    text = _text_input(body)
    # Do not mistake a quoted HTML doctype inside CDATA/comment for an XML DTD.
    declarations = re.sub(r'<!\[CDATA\[.*?\]\]>|<!--.*?-->', '', text, flags=re.S)
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', declarations, re.I):
        raise DataError('XML DTD/entity declarations are forbidden')
    parser = ET.XMLPullParser(events=('start', 'end'))
    depth = nodes = 0
    root = None
    try:
        for offset in range(0, len(text), 16384):
            parser.feed(text[offset:offset + 16384])
            for event, element in parser.read_events():
                if event == 'start':
                    depth += 1
                    nodes += 1
                    if depth > MAX_DEPTH or nodes > MAX_NODES:
                        raise DataError('XML depth/node budget exceeded')
                    if root is None:
                        root = element
                else:
                    depth -= 1
        parser.close()
    except ET.ParseError as exc:
        raise DataError('malformed XML feed') from exc
    if root is None:
        raise DataError('empty XML is not a recognized empty feed')
    return root


def _local(tag):
    return tag.rsplit('}', 1)[-1]


def _text(element):
    return ''.join(element.itertext()) if element is not None else None


def _content(element):
    if element is None:
        return None
    if not len(element):
        return element.text or ''
    # Atom XHTML retains inert serialized markup; no HTML is executed/rendered.
    return (element.text or '') + ''.join(ET.tostring(child, encoding='unicode') for child in element)


def _date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value.strip())
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        # Missing timezone is unknown; never manufacture UTC for source timestamps.
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def parse_feed(body):
    """Return normalized entries; recognized rss/channel or Atom/feed may be empty."""
    root = _xml(body)
    if root.tag == 'rss':
        channels = root.findall('channel')
        if len(channels) != 1:
            raise DataError('RSS requires one channel')
        rows, kind = channels[0].findall('item'), 'rss2'
    elif root.tag == f'{{{ATOM}}}feed':
        rows, kind = root.findall(f'{{{ATOM}}}entry'), 'atom'
    else:
        raise DataError('unrecognized feed schema; not a genuine empty result')
    result, seen = [], {}
    for index, row in enumerate(rows):
        prefix = f'rss/channel/item[{index}]' if kind == 'rss2' else f'atom:feed/atom:entry[{index}]'
        content_fields, locators = {}, {}
        if kind == 'rss2':
            title = _text(row.find('title')) or ''
            author_tag = f'{{{DC}}}creator' if _text(row.find(f'{{{DC}}}creator')) else 'author'
            author = _text(row.find(author_tag))
            date_tag = 'pubDate' if _text(row.find('pubDate')) else f'{{{DC}}}date'
            published = _text(row.find(date_tag))
            updated = _text(row.find('updated'))
            link = _text(row.find('link'))
            source_id = _text(row.find('guid'))
            identity_provenance = 'source guid' if source_id else 'source link'
            for field, tag in [('description', 'description'), ('content_encoded', f'{{{CONTENT}}}encoded')]:
                element = row.find(tag)
                if element is not None:
                    content_fields[field] = _content(element)
                    locators[field] = prefix + '/' + tag
            locators.update(title=prefix + '/title', author=prefix + '/' + author_tag,
                            published_at=prefix + '/' + date_tag, updated_at=prefix + '/updated',
                            link=prefix + '/link', source_id=prefix + ('/guid' if source_id else '/link'))
        else:
            title = _text(row.find(f'{{{ATOM}}}title')) or ''
            author = _text(row.find(f'{{{ATOM}}}author/{{{ATOM}}}name'))
            published = _text(row.find(f'{{{ATOM}}}published'))
            updated = _text(row.find(f'{{{ATOM}}}updated'))
            links = row.findall(f'{{{ATOM}}}link')
            alternate = next((e for e in links if e.get('rel', 'alternate') == 'alternate' and e.get('href')), None)
            link = alternate.get('href') if alternate is not None else None
            link_locator = prefix + f'/atom:link[{links.index(alternate)}]/@href' if alternate is not None else None
            source_id = _text(row.find(f'{{{ATOM}}}id'))
            identity_provenance = 'source atom:id' if source_id else 'source atom:link'
            for field in ('summary', 'content'):
                element = row.find(f'{{{ATOM}}}{field}')
                if element is not None:
                    content_fields[field] = _content(element)
                    locators[field] = prefix + '/atom:' + field
            locators.update(title=prefix + '/atom:title', author=prefix + '/atom:author/atom:name',
                            published_at=prefix + '/atom:published', updated_at=prefix + '/atom:updated',
                            link=link_locator, source_id=prefix + '/atom:id' if source_id else link_locator)
        source_id = (source_id or link or '').strip()
        if not source_id:
            source_id = hashlib.sha256(ET.tostring(row, encoding='utf-8')).hexdigest()
            identity_provenance = 'derived entry XML SHA-256; no source-provided stable identity'
            locators['source_id'] = None
        parts = []
        for value in content_fields.values():
            if value and value not in parts:
                parts.append(value)
        entry = {'source_id': source_id, 'source_id_provenance': identity_provenance,
                 'title': title, 'author': author or None,
                 'published_at': published, 'published_at_utc': _date(published),
                 'updated_at': updated, 'updated_at_utc': _date(updated),
                 'link': link, 'link_provenance': 'source-provided URL or reference; DATA only, not fetched' if link else None,
                 'content': '\n\n'.join(parts), 'content_fields': content_fields,
                 'raw_locator': prefix, 'raw_index': index, 'feed_format': kind,
                 'field_locators': locators, 'duplicate_occurrences': 0,
                 'duplicate_conflicting_content': False}
        if source_id in seen:
            prior = result[seen[source_id]]
            prior['duplicate_occurrences'] += 1
            prior['duplicate_conflicting_content'] |= any(prior[k] != entry[k] for k in ('title', 'author', 'content', 'published_at'))
            continue
        seen[source_id] = len(result)
        result.append(entry)
    return result


def _same_host_feed_url(value, base_url):
    try:
        absolute = urljoin(base_url, value)
        parsed = urlsplit(absolute)
        if (parsed.scheme != 'https' or parsed.hostname != FEED_HOST or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment):
            return None
        return absolute
    except ValueError:
        return None


class _FeedLinks(HTMLParser):
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url, self.links = base_url, []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        href = attrs.get('href')
        if not isinstance(href, str) or tag not in ('a', 'link'):
            return
        kind = attrs.get('type', '').lower().split(';', 1)[0]
        alternate = 'alternate' in attrs.get('rel', '').lower().split()
        suffix = urlsplit(href).path.lower().endswith(('.rss', '.xml', '.atom'))
        if not ((alternate and kind in ('application/rss+xml', 'application/atom+xml')) or suffix):
            return
        url = _same_host_feed_url(href, self.base_url)
        if url and url not in self.links and len(self.links) < 32:
            self.links.append(url)


def discover_feeds(html, base_url):
    """Return actual declared feed links on the exact approved host; no guessed paths."""
    if not _same_host_feed_url(base_url, base_url):
        raise DataError('discovery base URL outside exact approved HTTPS host')
    parser = _FeedLinks(base_url)
    try:
        parser.feed(_text_input(html))
    except (ValueError, RecursionError) as exc:
        raise DataError('invalid HTML feed discovery document') from exc
    return parser.links
