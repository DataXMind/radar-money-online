"""Pure v4 T2.5a/b classification of caller-reviewed public source captures.

The caller must verify captured bytes, hashes, exact locators, quoted fields,
entity mappings and URL approvals before evaluation. Approval records authorize
exact URLs, never an entire host. This module performs no I/O or checkout and
does not establish a real transaction, deployed checkout or founder identity.
The historical v2 evaluator remains unchanged.
"""
import ipaddress
import re
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from urllib.parse import parse_qsl, urlsplit


PROVIDERS = frozenset(('stripe', 'paddle', 'lemonsqueezy'))
OBSERVATIONS = frozenset(('CURRENT_PRODUCT_DOCUMENTATION',
                          'CURRENT_PRODUCT_IMPLEMENTATION',
                          'CURRENT_PRODUCT_WEBPAGE'))
REVIEW = 'CONFIRMED_SOURCE_STATEMENT'
SECRET_QUERY_KEYS = frozenset(('token', 'access_token', 'api_key', 'key',
                              'client_secret', 'secret', 'password',
                              'authorization', 'auth'))
CADENCES = frozenset(('monthly', 'annual', 'weekly', 'daily', 'one_time',
                     'usage_based', 'per_unit'))


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _public_url(value):
    if not _text(value) or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme != 'https' or not host or not '.' in host
                or url.username or url.password or url.fragment
                or url.port not in (None, 443) or '\\' in value
                or host == 'localhost' or host.endswith(('.localhost', '.local', '.internal'))
                or any(k.lower() in SECRET_QUERY_KEYS for k, _ in parse_qsl(url.query))):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def _source_allowed(value, approved_urls):
    return (_public_url(value)
            and (urlsplit(value).hostname == 'hn.algolia.com' or value in approved_urls))


def _trace(proof, product, approved_urls):
    if not isinstance(proof, dict):
        return False
    raw_path = proof.get('raw_response_path')
    if not _text(raw_path) or any(ord(ch) < 32 or ord(ch) == 127 for ch in raw_path):
        return False
    path = PurePosixPath(raw_path.replace('\\', '/'))
    return (proof.get('present') is True and proof.get('product') == product
            and proof.get('review_status') == REVIEW
            and proof.get('observation_type') in OBSERVATIONS
            and _source_allowed(proof.get('source_url'), approved_urls)
            and not path.is_absolute() and len(path.parts) > 2
            and path.parts[:2] == ('artifacts', 'live-evidence-v4')
            and '..' not in path.parts and ':' not in str(path)
            and path.suffix == '.body'
            and isinstance(proof.get('raw_response_sha256'), str)
            and bool(re.fullmatch(r'[a-f0-9]{64}', proof['raw_response_sha256']))
            and _text(proof.get('raw_locator')) and _text(proof.get('quote')))


def _reference(proof):
    return (proof['evidence_id'] if _text(proof.get('evidence_id')) else
            proof['raw_response_path'].replace('\\', '/') + '#' + proof['raw_locator'])


def _price(price):
    if not isinstance(price, dict):
        return False
    value = price.get('amount')
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return False
    try:
        amount = Decimal(str(value))
        return (amount.is_finite() and amount > 0
                and isinstance(price.get('currency'), str)
                and bool(re.fullmatch('[A-Z]{3}', price['currency']))
                and price.get('cadence') in CADENCES)
    except (InvalidOperation, ValueError):
        return False


def evaluate_infrastructure(candidate, approved_urls=()):
    """Classify a reviewed current product as T2.5a, optionally T2.5b.

    ``approved_urls`` contains exact, separately user-approved fetch URLs.
    Integration requires integration_status=CURRENT_PRODUCT_INTEGRATION_REVIEWED;
    a provider mention alone does not meet it. Pricing requires a captured real
    paid plan, prices (amount/currency/cadence), and placeholder=False. Optional
    checkout requires a separately approved static checkout URL and flow review;
    signup links and executed/dynamic checkout do not qualify. A checkout GAP
    preserves independently complete T2.5a. Run-level minimum-count gates remain
    the merge caller's responsibility.
    """
    base = {'tier': None, 'verdict': 'RESEARCH_DRAFT_ONLY', 'eligible': False,
            'source_statement_review_only': True, 'deployed_checkout_verified': False,
            'transaction_verified': False, 'checkout_executed': False,
            'verified_payment': False, 'founder_identity_verified': False,
            'longitudinal_t7_t14_verified': False, 'checkout_flow_verified': False,
            'evidence_ids': [], 'reasons': [], 'checkout_gaps': []}
    if (not isinstance(approved_urls, (tuple, list, set, frozenset))
            or any(not _public_url(url) for url in approved_urls)):
        return {**base, 'reasons': ['INVALID_EXACT_URL_APPROVALS']}
    approved_urls = frozenset(approved_urls)
    if not isinstance(candidate, dict):
        return {**base, 'reasons': ['INVALID_CANDIDATE']}
    product, founder = candidate.get('product'), candidate.get('founder')
    if not _text(product) or not _text(founder):
        return {**base, 'reasons': ['PRODUCT_AND_SOURCE_ATTRIBUTED_FOUNDER_REQUIRED']}
    context = candidate.get('current_product_context')
    if not _trace(context, product, approved_urls):
        return {**base, 'reasons': ['CURRENT_PRODUCT_CONTEXT_MISSING_OR_INVALID']}
    if (context.get('context') != 'CURRENT_PRODUCT'
            or context.get('scaffold_only') is not False
            or context.get('demo_only') is not False
            or context.get('founder') != founder
            or context.get('founder_product_linkage_reviewed') is not True
            or not _public_url(context.get('live_product_url'))):
        return {**base, 'reasons': ['CURRENT_PRODUCT_FOUNDER_LIVE_URL_LINKAGE_NOT_ESTABLISHED']}
    components = candidate.get('components')
    if not isinstance(components, dict):
        return {**base, 'reasons': ['INTEGRATION_AND_PRICING_REQUIRED']}
    integration, pricing = components.get('integration'), components.get('pricing')
    reasons = []
    if not _trace(integration, product, approved_urls):
        reasons.append('INTEGRATION_MISSING_OR_INVALID')
    elif integration.get('integration_status') != 'CURRENT_PRODUCT_INTEGRATION_REVIEWED':
        reasons.append('PROVIDER_MENTION_IS_NOT_REVIEWED_INTEGRATION')
    if not _trace(pricing, product, approved_urls):
        reasons.append('PRICING_MISSING_OR_INVALID')
    elif (pricing.get('pricing_status') != 'CURRENT_PAID_PLAN_REVIEWED'
          or pricing.get('observation_type') != 'CURRENT_PRODUCT_WEBPAGE'
          or pricing.get('source_url') not in approved_urls
          or urlsplit(pricing.get('source_url')).hostname == 'hn.algolia.com'
          or pricing.get('placeholder') is not False
          or not isinstance(pricing.get('prices'), list) or not pricing['prices']
          or not all(_price(price) for price in pricing['prices'])):
        reasons.append('CONCRETE_CURRENT_NON_PLACEHOLDER_PAID_PRICING_REQUIRED')
    if reasons:
        return {**base, 'reasons': reasons}
    provider = integration.get('provider')
    if not isinstance(provider, str) or provider.lower() not in PROVIDERS:
        return {**base, 'reasons': ['SUPPORTED_PAYMENT_PROVIDER_REQUIRED']}
    provider = provider.lower()
    other = pricing.get('provider')
    if other is not None and (not isinstance(other, str) or other.lower() != provider):
        return {**base, 'reasons': ['CROSS_PROVIDER_PRICING_LINKAGE']}
    proofs = [context, integration, pricing]
    checkout = components.get('checkout')
    checkout_gaps = []
    checkout_ok = False
    if checkout is None or (isinstance(checkout, dict) and checkout.get('present') is False):
        checkout_gaps.append('STATIC_CHECKOUT_NOT_REVIEWED_OPTIONAL_FOR_T25A')
    elif not _trace(checkout, product, approved_urls):
        checkout_gaps.append('CHECKOUT_TRACE_MISSING_OR_INVALID')
    else:
        checkout_url = checkout.get('checkout_url')
        checkout_provider = checkout.get('provider')
        if (not isinstance(checkout_provider, str) or checkout_provider.lower() != provider):
            checkout_gaps.append('CROSS_PROVIDER_CHECKOUT_LINKAGE')
        if (checkout.get('checkout_kind') != 'STATIC_CHECKOUT_URL'
                or checkout.get('static_flow_reviewed') is not True
                or checkout.get('checkout_executed', False) is not False
                or checkout.get('signup_only', False) is not False):
            checkout_gaps.append('SIGNUP_DYNAMIC_OR_EXECUTED_FLOW_IS_NOT_STATIC_CHECKOUT_PROOF')
        if (not _public_url(checkout_url) or checkout_url not in approved_urls):
            checkout_gaps.append('EXACT_CHECKOUT_URL_APPROVAL_REQUIRED')
        checkout_ok = not checkout_gaps
    if checkout_ok:
        proofs.append(checkout)
    references = list(dict.fromkeys(_reference(proof) for proof in proofs))
    return {**base, 'tier': 'T2.5b' if checkout_ok else 'T2.5a',
            'verdict': 'EMERGING', 'eligible': True,
            'checkout_flow_verified': checkout_ok, 'checkout_gaps': checkout_gaps,
            'evidence_ids': references,
            'reasons': ['CURRENT_PRODUCT_INTEGRATION_AND_REAL_PRICING_REVIEWED',
                        *(['STATIC_CHECKOUT_FLOW_REVIEWED_WITHOUT_EXECUTION'] if checkout_ok else []),
                        'INFRASTRUCTURE_OBSERVED_NOT_VERIFIED_TRANSACTION']}
