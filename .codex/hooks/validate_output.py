"""Validate structured draft research outputs, without treating other chat as research."""
import hashlib
import re
from urllib.parse import urlsplit
from gold_common import ROOT, cli, parse_json


def validate(doc, root=ROOT):
    if not isinstance(doc, dict):
        raise ValueError('research output must be an object')
    if doc.get('status') != 'RESEARCH_DRAFT_ONLY':
        raise ValueError('option B requires RESEARCH_DRAFT_ONLY')
    for name, limit in [('raw_items', 15), ('claims', 8), ('opportunities', 5)]:
        if not isinstance(doc.get(name), list) or len(doc[name]) > limit:
            raise ValueError('invalid/over-budget ' + name)
    if doc['opportunities']:
        raise ValueError('option B cannot qualify opportunities')
    if not isinstance(doc.get('gaps'), list) or not doc['gaps'] or any(not isinstance(x, str) or not x.strip() for x in doc['gaps']):
        raise ValueError('explicit gaps required')
    evidence = set()
    for item in doc['raw_items']:
        if not isinstance(item, dict) or not isinstance(item.get('evidence_id'), str) or not item['evidence_id'] or item['evidence_id'] in evidence:
            raise ValueError('missing/duplicate evidence ID')
        url = urlsplit(item.get('url', ''))
        if url.scheme != 'https' or url.hostname not in ('github.com', 'hn.algolia.com', 'news.ycombinator.com') or url.username or url.password or url.port not in (None, 443):
            raise ValueError('invalid source URL')
        relative = item.get('response_body')
        if not isinstance(relative, str):
            raise ValueError('raw response path missing')
        raw = (root / relative).resolve()
        if not raw.is_relative_to((root / 'artifacts').resolve()) or not raw.is_file() or raw.stat().st_size > 4_000_000:
            raise ValueError('raw response path invalid')
        expected = item.get('response_sha256')
        if not isinstance(expected, str) or not re.fullmatch('[a-f0-9]{64}', expected) or hashlib.sha256(raw.read_bytes()).hexdigest() != expected:
            raise ValueError('raw response checksum mismatch')
        evidence.add(item['evidence_id'])
    claims = set()
    for claim in doc['claims']:
        if not isinstance(claim, dict) or not isinstance(claim.get('claim_id'), str) or not claim['claim_id'] or claim['claim_id'] in claims:
            raise ValueError('missing/duplicate claim ID')
        if not isinstance(claim.get('statement'), str) or not claim['statement'].strip():
            raise ValueError('claim statement required')
        refs = claim.get('evidence_ids')
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in evidence for ref in refs):
            raise ValueError('claim without source evidence')
        if claim.get('verdict') == 'EMERGING':
            raise ValueError('option B metadata cannot establish EMERGING')
        claims.add(claim['claim_id'])
    return True


def handle(event, root=ROOT):
    message = event.get('last_assistant_message')
    if message is None:
        return {'systemMessage': 'Output validation skipped: no final assistant message supplied.'}
    if not isinstance(message, str):
        raise ValueError('invalid final message')
    body = message.strip()
    if body.startswith('```json') and body.endswith('```'):
        body = body[7:-3].strip()
    if not body.startswith('{'):
        return {'systemMessage': 'Not a structured research output; no research validation PASS is claimed.'}
    try:
        doc = parse_json(body)
        # JSON that is not research (e.g. a config explanation) is out of scope.
        if isinstance(doc, dict) and not ({'status', 'claims', 'opportunities'} & set(doc)):
            return {'systemMessage': 'JSON is outside the research-output contract; not validated.'}
        validate(doc, root)
    except (ValueError, OSError, KeyError, TypeError, RecursionError):
        if event.get('stop_hook_active') is True:
            return {'continue': False, 'stopReason': 'Research output still invalid after one correction; stop for human review.'}
        return {'decision': 'block', 'reason': 'Research output failed validation. Return draft with empty opportunities, bounded claims and verifiable raw evidence references; do not invent missing data.'}
    return {'systemMessage': 'Structured draft output validation PASS (shape/hash checks, not independent truth verification).'}


if __name__ == '__main__':
    raise SystemExit(cli(handle))
