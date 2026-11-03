"""Offline trace verification and tier evaluation for the one live v2 capture."""
import base64
import hashlib
import json
import re
from pathlib import Path

from .core import DataError, strict_json
from .evidence_tiers import V2_HOSTS, evaluate_candidate
from .indie_run import load, sha
from .live_shared import public_url
from .live_v2_github import decode_readme, parse_repositories, signals
from .live_v2_hn import parse_response
from .payment_infra import evaluate_infrastructure

OUT = Path('artifacts/live-evidence-v2')


def jsonl(path):
    if path.stat().st_size > 4_000_000:
        raise DataError('JSONL exceeds byte budget')
    return [strict_json(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def response(root, proof):
    path = (root / proof['raw_response_path']).resolve()
    allowed = [root.resolve() / OUT / work / 'requests' for work in ('ws1', 'ws2')]
    if (not any(path.is_relative_to(folder) for folder in allowed) or path.suffix != '.body'
            or path.stat().st_size > 4_000_000 or sha(path) != proof['raw_response_sha256']):
        raise DataError('CRITICAL: v2 raw response path/hash mismatch')
    meta = load(path.with_suffix('.meta.json'))
    public_url(meta['url'], V2_HOSTS)
    url = proof.get('source_url', proof.get('source_request_url'))
    if (url != meta['url'] or meta['sha256'] != sha(path) or meta['bytes'] != path.stat().st_size
            or meta['status'] != 200 or meta.get('error_response') is not False
            or ('retrieved_at' in proof and proof['retrieved_at'] != meta['retrieved_at'])):
        raise DataError('CRITICAL: v2 response provenance mismatch')
    return path, strict_json(path.read_text(encoding='utf-8')), meta


def checked_record(root, item):
    path, doc, _ = response(root, item)
    match = re.fullmatch(r'(items|hits)\[(\d+)\]', item['raw_locator'])
    if not match:
        raise DataError('record locator is not an exact raw row')
    index = int(match[2])
    try:
        row = doc[match[1]][index]
    except (KeyError, IndexError, TypeError) as exc:
        raise DataError('record locator missing in raw') from exc
    if item['source'] == 'github_repository':
        parse_repositories(path.read_text(encoding='utf-8'))
        if (match[1] != 'items' or str(row['id']) != item['source_id'] or row['full_name'] != item['repo']
                or row['html_url'] != item['url'] or row['topics'] != item['topics']
                or (row.get('description') or row['full_name']) != item['title']):
            raise DataError('GitHub identity/metadata differs from raw')
        readme = item.get('readme')
        if readme is not None:
            readme_path, readme_doc, _ = response(root, readme)
            parsed, text = decode_readme(readme_path.read_text(encoding='utf-8'))
            blob = base64.b64decode(''.join(parsed['content'].split()), validate=True)
            git_bytes = b'blob ' + str(len(blob)).encode() + b'\0' + blob
            git_hash = hashlib.sha1(git_bytes).hexdigest() if len(parsed['sha']) == 40 else hashlib.sha256(git_bytes).hexdigest()
            if (parsed['sha'] != git_hash or readme['blob_sha'] != parsed['sha'] or readme['path'] != parsed['path']
                    or readme['decoded_sha256'] != hashlib.sha256(text.encode('utf-8')).hexdigest()
                    or not text.startswith(readme['excerpt']) or readme['component_signals'] != signals(text)
                    or readme['source_request_url'] != 'https://api.github.com/repos/' + item['repo'] + '/readme'
                    or not readme_doc['url'].startswith('https://api.github.com/repos/' + item['repo'] + '/contents/')):
                raise DataError('README identity/blob/excerpt/signals differ from raw')
    elif item['source'] == 'hn':
        if match[1] != 'hits':
            raise DataError('HN locator outside hits')
        protocol_path = root / OUT / 'ws2/protocol.json'
        protocol = load(protocol_path)
        query = next((q for q in protocol['queries'] if q['url'] == item['source_request_url']), None)
        if query is None:
            raise DataError('HN query not in frozen protocol')
        expected = parse_response(path.read_text(encoding='utf-8'), query, protocol)[index]
        if any(item.get(key) != value for key, value in expected.items()) or item['protocol_sha256'] != sha(protocol_path):
            raise DataError('HN normalized fields differ from raw/protocol')
    else:
        raise DataError('unknown v2 source')
    return row


def checked_quote(root, proof):
    """Resolve exact field/decoded line; never eval a source-provided locator."""
    path, doc, _ = response(root, proof)
    locator = proof.get('raw_locator', '')
    match = re.fullmatch(r'decoded_readme\.lines\[(\d+)\]', locator)
    if match:
        _, text = decode_readme(path.read_text(encoding='utf-8'))
        index = int(match[1]) - 1  # Documented one-based decoded README line.
        lines = text.splitlines()
        if not 0 <= index < len(lines):
            raise DataError('README quote line outside raw')
        value = lines[index]
    else:
        match = re.fullmatch(r'(items|hits)\[(\d+)\]\.([a-zA-Z_]+)', locator)
        if not match:
            raise DataError('unsupported exact field quote locator')
        try:
            value = doc[match[1]][int(match[2])][match[3]]
        except (KeyError, IndexError, TypeError) as exc:
            raise DataError('quote field missing from raw') from exc
    quote = proof.get('quote')
    if not isinstance(quote, str) or not quote or not isinstance(value, str) or quote not in value:
        raise DataError('quoted statement is absent from exact raw field/line')
    return value


def bind_proof(item, proof):
    """A valid quote from a different row/repo cannot support this evidence ID."""
    references = [item]
    if item.get('readme'):
        references.append(item['readme'])
    for reference in references:
        if (proof.get('raw_response_path') == reference.get('raw_response_path')
                and proof.get('raw_response_sha256') == reference.get('raw_response_sha256')
                and proof.get('source_url') == reference.get('source_request_url')):
            if reference is item and proof.get('raw_locator', '').startswith(item['raw_locator'] + '.'):
                return
            if reference is not item and re.fullmatch(r'decoded_readme\.lines\[\d+\]', proof.get('raw_locator', '')):
                return
    raise DataError('quote provenance does not belong to referenced evidence record')


def audit_requests(root):
    counts, sources = {}, []
    for work, host, cap in (('ws1', 'api.github.com', 12), ('ws2', 'hn.algolia.com', 12)):
        folder = root / OUT / work
        protocol = load(folder / 'protocol.json')
        events = jsonl(folder / 'requests/requests.jsonl')
        starts = [e for e in events if e['event'] == 'request_start']
        ingress = [e for e in events if e['event'] == 'data_ingress']
        if (not 0 < len(starts) <= cap or len(ingress) != len(starts)
                or len({e['request_id'] for e in starts}) != len(starts)
                or {e['request_id'] for e in starts} != {e['request_id'] for e in ingress}
                or len(list((folder / 'requests').glob('*.meta.json'))) != len(ingress)):
            raise DataError('CRITICAL: request/ingress budget or identity mismatch')
        for event in ingress:
            public_url(event['url'], (host,))
            if sum(e['request_id'] == event['request_id'] and e['url'] == event['url'] for e in starts) != 1:
                raise DataError('CRITICAL: request/ingress linkage mismatch')
            path = folder / 'requests' / event['body_file']
            proof = {'raw_response_path': path.relative_to(root).as_posix(),
                     'raw_response_sha256': event['sha256'], 'source_url': event['url']}
            _, _, meta = response(root, proof)
            if any(event.get(k) != value for k, value in meta.items()):
                raise DataError('CRITICAL: logged ingress differs from metadata')
            sources.append({'workstream': work, **meta, 'raw_response_path': proof['raw_response_path']})
        counts[work] = len(starts)
        if not protocol.get('queries'):
            raise DataError('frozen query protocol missing')
    return counts, sources


def evaluate_review(root, records, review):
    """Review input stays separate from source data and must map to captured rows."""
    by_id = {r['evidence_id']: r for r in records}
    candidates = review['candidates']
    if (not isinstance(candidates, list) or len(candidates) != len(records)
            or {c['evidence_id'] for c in candidates} != set(by_id)):
        raise DataError('review must cover each captured record once')
    evaluations, opportunities = [], []
    for candidate in candidates:
        item = by_id[candidate['evidence_id']]
        if item['source'] == 'github_repository' and candidate['product'] != item['repo']:
            raise DataError('review product must preserve captured repository identity')
        infra = candidate.get('infrastructure', {'product': candidate['product']})
        for proof in [infra.get('current_product_context'), *infra.get('components', {}).values()]:
            if isinstance(proof, dict) and proof.get('quote'):
                bind_proof(item, proof)
                checked_quote(root, proof)
                if proof.get('evidence_id') != item['evidence_id'] or proof.get('product') != candidate['product']:
                    raise DataError('component cross-record/product linkage mismatch')
        result25 = evaluate_infrastructure(infra)
        historical = candidate.get('transaction_or_history', {'product': candidate['product'], 'points': []})
        proofs = historical.get('points', []) + ([historical['t1_proof']] if historical.get('t1_proof') else [])
        for proof in proofs:
            if proof.get('evidence_id') not in by_id:
                raise DataError('economic observation references unknown record')
            bind_proof(by_id[proof['evidence_id']], proof)
            checked_quote(root, proof)
            # Each normalized economic field needs an explicit source quote/value map.
            required = (('product', 'founder', 'metric', 'currency', 'cadence', 'value', 'period_start', 'period_end', 'observed_at')
                        if proof in historical.get('points', []) else ('product', 'buyer', 'transaction_at', 'proof_type', 'payment_status'))
            for field in required:
                mapping = proof.get('field_quotes', {}).get(field, {})
                if mapping.get('value') != proof.get(field):
                    raise DataError('economic field mapping value mismatch')
                checked_quote(root, {**proof, 'quote': mapping.get('quote')})
        if proofs and not all(p.get('field_quotes') for p in proofs):
            raise DataError('economic observations need reviewed source field mappings')
        result12 = evaluate_candidate(historical, allowed_hosts=V2_HOSTS)
        result = result12 if result12['eligible'] else result25
        # Metadata is T3/HYPED, separate from eligible opportunities.
        if not result['eligible']:
            result = {**result, 'tier': 'T3', 'verdict': 'HYPED',
                      'reasons': result['reasons'] + ['CAPTURED_SOURCE_METADATA_ONLY_NOT_QUALIFIED_T2_5']}
        entry = {'evidence_id': item['evidence_id'], 'product': candidate['product'],
                 'source_url': item['url'], **result, 'component_review': candidate.get('component_review', {}),
                 'review_gaps': candidate.get('review_gaps', [])}
        evaluations.append(entry)
        if result['eligible']:
            paid = bool(result.get('verified_payment'))
            transaction = historical.get('t1_proof', {}) if paid else {}
            opportunities.append({**entry, 'buyer_evidence': {'present': paid, 'proof_type': transaction.get('proof_type'), 'url': transaction.get('source_url')},
                                  'payment_evidence': {'present': paid, 'proof_type': transaction.get('proof_type'), 'url': transaction.get('source_url')},
                                  'trend_evidence': {'present': False, 'cohort': None, 't0': None, 't_plus': None, 'metric': None},
                                  'payment_infrastructure_evidence': infra,
                                  'revenue_history_evidence': historical if result.get('tier') == 'T2' else None})
    opportunities.sort(key=lambda r: ({'T1': 0, 'T2': 1, 'T2.5': 2}[r['tier']], r['evidence_id']))
    opportunities = opportunities[:5]
    claims = review['claims']
    if not isinstance(claims, list) or len(claims) > 8:
        raise DataError('claim budget exceeded')
    for claim in claims:
        if claim['evidence_id'] not in by_id:
            raise DataError('claim references unknown record')
        bind_proof(by_id[claim['evidence_id']], claim)
        checked_quote(root, claim)
    return {'evaluations': evaluations, 'opportunities': opportunities, 'claims': claims}


def make_review(root, components):
    """Normalize human component review; never infer qualification from keywords."""
    github = jsonl(root / OUT / 'github_evidence.jsonl')
    hn = jsonl(root / OUT / 'hn_evidence.jsonl')
    reviews = {r['evidence_id']: r for r in components['github_reviews']}
    hn_reviews = {r['evidence_id']: r for r in components['hn_reviews']}
    if set(reviews) != {r['evidence_id'] for r in github} or set(hn_reviews) != {r['evidence_id'] for r in hn}:
        raise DataError('component review does not cover captured records')
    candidates, claims = [], []
    selected = {'V2-GH01', 'V2-GH03', 'V2-GH05', 'V2-GH06', 'V2-GH07', 'V2-GH08', 'V2-HN01', 'V2-HN03'}
    for item in github:
        review = reviews[item['evidence_id']]
        if review['product'] != item['repo']:
            raise DataError('human component review product mismatch')
        assessment = review['assessments']
        proofs = {}
        for name in ('current_product_context', 'integration', 'pricing', 'checkout'):
            evidence = assessment[name]
            if type(evidence.get('present')) is not bool:
                raise DataError('component present must be a reviewed boolean')
            proof = {**{k: review['references'][k] for k in ('source_url', 'raw_response_path', 'raw_response_sha256')},
                     'evidence_id': item['evidence_id'], 'product': item['repo'], 'present': evidence['present'],
                     'review_status': 'CONFIRMED_SOURCE_STATEMENT', 'observation_type': 'CURRENT_PRODUCT_DOCUMENTATION',
                     'raw_locator': f"decoded_readme.lines[{evidence['decoded_readme_line']}]", 'quote': evidence['quote']}
            checked_quote(root, proof)
            proofs[name] = proof
        context = proofs.pop('current_product_context')
        context.update(context='CURRENT_PRODUCT' if context['present'] else 'PRODUCT_CONTEXT_NOT_ESTABLISHED',
                       scaffold_only=not context['present'])
        providers = re.findall(r'\b(stripe|paddle|lemon\s?squeezy)\b', proofs['integration']['quote'], re.I)
        proofs['integration']['provider'] = providers[0].lower().replace(' ', '') if providers else None
        candidates.append({'evidence_id': item['evidence_id'], 'product': item['repo'],
                           'infrastructure': {'product': item['repo'], 'current_product_context': context, 'components': proofs},
                           'transaction_or_history': {'product': item['repo'], 'points': []},
                           'component_review': assessment,
                           'review_gaps': [v['reason'] for v in assessment.values() if not v['present']]})
        if item['evidence_id'] in selected:
            proof = proofs['integration']
            claims.append({'claim_id': f'V2-C{len(claims)+1:02d}', **proof,
                           'kind': 'OBSERVED_SOURCE_STATEMENT', 'verdict': 'HYPED',
                           'statement': 'Captured README contains this documentation statement; it does not establish a qualified paid product.'})
    for item in hn:
        review = hn_reviews[item['evidence_id']]
        checked_quote(root, review)
        candidates.append({'evidence_id': item['evidence_id'], 'product': item['title'],
                           'transaction_or_history': {'product': item['title'], 'points': []},
                           'review_gaps': [review['reason']]})
        if item['evidence_id'] in selected:
            claims.append({'claim_id': f'V2-C{len(claims)+1:02d}',
                           **{k: review[k] for k in ('evidence_id', 'source_url', 'raw_response_path', 'raw_response_sha256', 'raw_locator', 'quote')},
                           'kind': 'OBSERVED_SOURCE_STATEMENT', 'verdict': 'HYPED',
                           'statement': 'Captured HN statement is source-attributed only, not verified founder, buyer, revenue or payment infrastructure.'})
    return {'reviewed_at': components['reviewed_at'], 'review_mode': components['review_mode'],
            'claim_selection': 'Purposive six GitHub documentation statements plus two HN statements after reviewing all15; not a prevalence estimate.',
            'candidates': candidates, 'claims': claims}


def build_ledger(root, review):
    root = Path(root).resolve()
    counts, responses = audit_requests(root)
    github = jsonl(root / OUT / 'github_evidence.jsonl')
    hn = jsonl(root / OUT / 'hn_evidence.jsonl')
    records = github + hn
    if (len(github) > 8 or len(hn) > 7 or len(records) > 15
            or len({(r['source'], r['source_id']) for r in records}) != len(records)
            or len({r['evidence_id'] for r in records}) != len(records)):
        raise DataError('global record/identity cap exceeded')
    for item in records:
        checked_record(root, item)
    baseline = load(root / OUT / 'ws3/audit.json')
    if (baseline.get('integrity') != 'PASS' or baseline.get('baseline_records') != 15
            or baseline.get('baseline_excluded_from_discovery_merge') is not True
            or baseline.get('new_observations') != 0):
        raise DataError('CRITICAL: historical baseline audit failed')
    for name, digest in baseline['historical_files_sha256'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root / 'artifacts') or sha(path) != digest:
            raise DataError('CRITICAL: baseline changed since read-only audit')
    result = evaluate_review(root, records, review)
    return {'status': 'RESEARCH_WITH_EMERGING_CANDIDATES' if result['opportunities'] else 'RESEARCH_DRAFT_ONLY',
            'run_id': 'live-evidence-v2', 'raw_items': records, 'raw_count': len(records),
            'claim_count': len(result['claims']), 'opportunity_count': len(result['opportunities']),
            'source_counts': {'github': len(github), 'hn': len(hn)}, 'request_counts': counts,
            'responses': responses, **result, 'baseline': {'records': 15, 'merged': False,
             'snapshot_sha256': baseline['snapshot_sha256'], 't7_executed': False, 't14_executed': False}}
