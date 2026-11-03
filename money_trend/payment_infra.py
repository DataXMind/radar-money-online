"""Pure T2.5 gate for caller-reviewed current-product documentation/code.

The caller verifies captured bytes, raw locators, quotes and field mappings.
This function cannot establish deployed checkout availability or payments. It
does not fetch URLs, execute checkout/code, read files, or infer from keywords.
"""
import re
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlsplit

HOSTS = frozenset(('api.github.com', 'github.com', 'hn.algolia.com'))
PROVIDERS = frozenset(('stripe', 'paddle', 'lemonsqueezy'))
OBSERVATIONS = frozenset(('CURRENT_PRODUCT_DOCUMENTATION', 'CURRENT_PRODUCT_IMPLEMENTATION'))
COMPONENTS = ('integration', 'pricing', 'checkout')
REVIEW = 'CONFIRMED_SOURCE_STATEMENT'
SECRET_QUERY_KEYS = frozenset(('token', 'access_token', 'api_key', 'key', 'client_secret',
                              'secret', 'password', 'authorization', 'auth'))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _public_source(value):
    if not _text(value) or any(ord(ch) < 32 for ch in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and parsed.hostname in HOSTS
                and not parsed.username and not parsed.password and not parsed.fragment
                and parsed.port in (None, 443)
                and not any(key.lower() in SECRET_QUERY_KEYS for key, _ in parse_qsl(parsed.query)))
    except ValueError:
        return False


def _trace(proof, product):
    if not isinstance(proof, dict):
        return False
    raw_path = proof.get('raw_response_path')
    if not _text(raw_path) or any(ord(ch) < 32 for ch in raw_path):
        return False
    path = PurePosixPath(raw_path.replace('\\', '/'))
    return (proof.get('present') is True and proof.get('product') == product
            and proof.get('review_status') == REVIEW
            and proof.get('observation_type') in OBSERVATIONS
            and _public_source(proof.get('source_url'))
            and not path.is_absolute() and len(path.parts) > 2
            and path.parts[:2] == ('artifacts', 'live-evidence-v2')
            and '..' not in path.parts and ':' not in str(path)
            and isinstance(proof.get('raw_response_sha256'), str)
            and bool(re.fullmatch(r'[a-f0-9]{64}', proof['raw_response_sha256']))
            and _text(proof.get('raw_locator')) and _text(proof.get('quote')))


def _reference(proof):
    """Preserve provided evidence IDs; otherwise use a derived raw locator ref."""
    return (proof['evidence_id'] if _text(proof.get('evidence_id')) else
            proof['raw_response_path'].replace('\\', '/') + '#' + proof['raw_locator'])


def evaluate_infrastructure(candidate):
    """Return EMERGING only for all three components of one current product.

    Review flags attest a source statement/implementation, not real usage,
    successful payments, independent confirmation, or prospective trend.
    """
    base = {'tier': None, 'verdict': 'RESEARCH_DRAFT_ONLY', 'eligible': False,
            'source_statement_review_only': True, 'deployed_checkout_verified': False,
            'transaction_verified': False, 'checkout_executed': False,
            'verified_payment': False, 'longitudinal_t7_t14_verified': False,
            'evidence_ids': [], 'reasons': []}
    if not isinstance(candidate, dict):
        return {**base, 'reasons': ['INVALID_CANDIDATE']}
    product = candidate.get('product')
    if not _text(product):
        return {**base, 'reasons': ['PRODUCT_REQUIRED']}
    context = candidate.get('current_product_context')
    if not _trace(context, product):
        return {**base, 'reasons': ['CURRENT_PRODUCT_CONTEXT_MISSING_OR_INVALID']}
    if context.get('context') != 'CURRENT_PRODUCT' or context.get('scaffold_only') is not False:
        return {**base, 'reasons': ['CURRENT_PRODUCT_NOT_ESTABLISHED_OR_SCAFFOLD_ONLY']}
    components = candidate.get('components')
    if not isinstance(components, dict):
        return {**base, 'reasons': ['THREE_REVIEWED_COMPONENTS_REQUIRED']}
    reasons = []
    for name in COMPONENTS:
        proof = components.get(name)
        if not _trace(proof, product):
            reasons.append(name.upper() + '_MISSING_OR_INVALID')
    if reasons:
        return {**base, 'reasons': reasons}
    provider = components['integration'].get('provider')
    if not isinstance(provider, str) or provider.lower() not in PROVIDERS:
        return {**base, 'reasons': ['SUPPORTED_PAYMENT_PROVIDER_REQUIRED']}
    # A pricing/checkout proof may explicitly name its provider. If supplied,
    # it must match integration; never silently join different billing stacks.
    for name in ('pricing', 'checkout'):
        other = components[name].get('provider')
        if other is not None and (not isinstance(other, str) or other.lower() != provider.lower()):
            return {**base, 'reasons': ['CROSS_PROVIDER_COMPONENT_LINKAGE']}
    references = list(dict.fromkeys(_reference(proof) for proof in (context, *(components[n] for n in COMPONENTS))))
    return {**base, 'tier': 'T2.5', 'verdict': 'EMERGING', 'eligible': True,
            'evidence_ids': references,
            'reasons': ['CURRENT_PRODUCT_PAYMENT_INTEGRATION_PRICING_AND_CHECKOUT_REVIEWED',
                        'INFRASTRUCTURE_OBSERVED_NOT_VERIFIED_TRANSACTION',
                        'DEPLOYMENT_AND_CHECKOUT_NOT_EXECUTED_OR_VERIFIED']}
