"""Synthetic policy/safety tests only; these are not live payment evidence."""
import copy
import unittest
from unittest.mock import patch

from money_trend.payment_infra_v4 import evaluate_infrastructure


PRICING = 'https://synthetic-product.test/pricing'
CHECKOUT = 'https://checkout.synthetic-product.test/paid-plan'


def proof(component, source='https://hn.algolia.com/api/v1/search?tags=show_hn'):
    return {'present': True, 'product': 'SYNTHETIC-PRODUCT',
            'review_status': 'CONFIRMED_SOURCE_STATEMENT',
            'observation_type': 'CURRENT_PRODUCT_DOCUMENTATION',
            'evidence_id': 'TEST-' + component,
            'source_url': source,
            'raw_response_path': 'artifacts/live-evidence-v4/TEST-ONLY/source.body',
            'raw_response_sha256': 'a' * 64,
            'raw_locator': 'hits[0].story_text.' + component,
            'quote': 'SYNTHETIC reviewed current-product statement: ' + component}


def candidate():
    context = {**proof('context'), 'context': 'CURRENT_PRODUCT', 'scaffold_only': False,
               'demo_only': False, 'founder': 'synthetic-founder-hn-account',
               'founder_product_linkage_reviewed': True,
               'live_product_url': 'https://synthetic-product.test/'}
    return {'product': 'SYNTHETIC-PRODUCT', 'founder': 'synthetic-founder-hn-account',
            'current_product_context': context,
            'components': {
                'integration': {**proof('integration'), 'provider': 'stripe',
                                'integration_status': 'CURRENT_PRODUCT_INTEGRATION_REVIEWED'},
                'pricing': {**proof('pricing', PRICING),
                            'observation_type': 'CURRENT_PRODUCT_WEBPAGE',
                            'pricing_status': 'CURRENT_PAID_PLAN_REVIEWED', 'placeholder': False,
                            'prices': [{'amount': '19', 'currency': 'USD', 'cadence': 'monthly'}]}}}


def with_checkout():
    doc = candidate()
    doc['components']['checkout'] = {**proof('checkout', CHECKOUT), 'provider': 'stripe',
                                     'checkout_url': CHECKOUT,
                                     'checkout_kind': 'STATIC_CHECKOUT_URL',
                                     'static_flow_reviewed': True}
    return doc


class PaymentInfrastructureV4Tests(unittest.TestCase):
    def test_a_requires_integration_and_real_pricing_not_checkout(self):
        result = evaluate_infrastructure(candidate(), [PRICING])
        self.assertEqual((result['tier'], result['verdict'], result['eligible']),
                         ('T2.5a', 'EMERGING', True))
        self.assertEqual(result['evidence_ids'], ['TEST-context', 'TEST-integration', 'TEST-pricing'])
        self.assertFalse(result['checkout_flow_verified'])

    def test_b_adds_reviewed_approved_static_checkout_only(self):
        result = evaluate_infrastructure(with_checkout(), [PRICING, CHECKOUT])
        self.assertEqual(result['tier'], 'T2.5b')
        self.assertTrue(result['checkout_flow_verified'])
        self.assertIn('TEST-checkout', result['evidence_ids'])
        for key in ('verified_payment', 'transaction_verified', 'checkout_executed',
                    'deployed_checkout_verified', 'founder_identity_verified',
                    'longitudinal_t7_t14_verified'):
            self.assertFalse(result[key])

    def test_pricing_pending_or_unfetched_never_qualifies(self):
        for change in ({'present': False}, {'pricing_status': 'PENDING_VERIFICATION'},
                       {'prices': []}, {'placeholder': True}, {'placeholder': 0}):
            doc = candidate()
            doc['components']['pricing'].update(change)
            with self.subTest(change=change):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_provider_mention_is_not_actual_integration(self):
        doc = candidate()
        doc['components']['integration']['integration_status'] = 'MENTION_ONLY'
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_price_in_hn_post_cannot_replace_captured_approved_pricing_page(self):
        doc = candidate()
        hn_url = 'https://hn.algolia.com/api/v1/search?tags=show_hn'
        doc['components']['pricing']['source_url'] = hn_url
        self.assertFalse(evaluate_infrastructure(doc, [PRICING, hn_url])['eligible'])
        doc = candidate()
        doc['components']['pricing']['observation_type'] = 'CURRENT_PRODUCT_DOCUMENTATION'
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])
        del doc['components']['integration']
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_missing_pricing_never_qualifies(self):
        doc = candidate()
        del doc['components']['pricing']
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_cross_product_required_components_or_founder_are_rejected(self):
        for name in ('context', 'integration', 'pricing'):
            doc = candidate()
            item = doc['current_product_context'] if name == 'context' else doc['components'][name]
            item['product'] = 'OTHER-PRODUCT'
            with self.subTest(name=name):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])
        doc = candidate()
        doc['current_product_context']['founder'] = 'other-founder'
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_cross_provider_pricing_rejects_a_checkout_only_downgrades_b(self):
        doc = candidate()
        doc['components']['pricing']['provider'] = 'paddle'
        self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])
        doc = with_checkout()
        doc['components']['checkout']['provider'] = 'paddle'
        result = evaluate_infrastructure(doc, [PRICING, CHECKOUT])
        self.assertEqual(result['tier'], 'T2.5a')
        self.assertIn('CROSS_PROVIDER_CHECKOUT_LINKAGE', result['checkout_gaps'])

    def test_same_domain_is_not_exact_pricing_url_approval(self):
        self.assertFalse(evaluate_infrastructure(candidate(), ['https://synthetic-product.test/'])['eligible'])
        self.assertFalse(evaluate_infrastructure(candidate(), [PRICING + '?approved=other'])['eligible'])
        self.assertFalse(evaluate_infrastructure(candidate())['eligible'])

    def test_signup_dynamic_or_executed_checkout_only_downgrades_to_a(self):
        for change in ({'checkout_kind': 'SIGN_UP'}, {'signup_only': True},
                       {'checkout_kind': 'DYNAMIC_CHECKOUT_SESSION'}, {'checkout_executed': True},
                       {'static_flow_reviewed': False}, {'present': False}):
            doc = with_checkout()
            doc['components']['checkout'].update(change)
            with self.subTest(change=change):
                result = evaluate_infrastructure(doc, [PRICING, CHECKOUT])
                self.assertEqual(result['tier'], 'T2.5a')
                self.assertFalse(result['checkout_flow_verified'])

    def test_checkout_link_itself_requires_exact_approval(self):
        doc = with_checkout()
        doc['components']['checkout']['source_url'] = PRICING
        result = evaluate_infrastructure(doc, [PRICING])
        self.assertEqual(result['tier'], 'T2.5a')
        self.assertIn('EXACT_CHECKOUT_URL_APPROVAL_REQUIRED', result['checkout_gaps'])

    def test_scaffold_demo_and_unreviewed_linkage_rejected(self):
        for change in ({'scaffold_only': True}, {'scaffold_only': 0}, {'demo_only': True},
                       {'founder_product_linkage_reviewed': False}, {'context': 'TUTORIAL'}):
            doc = candidate()
            doc['current_product_context'].update(change)
            with self.subTest(change=change):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_raw_path_hash_review_and_locator_boundaries(self):
        for key, value in (
            ('raw_response_path', 'artifacts/live-evidence-v2/old.body'),
            ('raw_response_path', 'artifacts/live-evidence-v4/../other/raw.body'),
            ('raw_response_path', '/artifacts/live-evidence-v4/raw.body'),
            ('raw_response_path', 'C:/secret.body'),
            ('raw_response_path', 'artifacts/live-evidence-v4evil/raw.body'),
            ('raw_response_path', 'artifacts/live-evidence-v4/raw.json'),
            ('raw_response_sha256', 'invalid'), ('raw_locator', ''), ('quote', ''),
            ('review_status', 'SOURCE_SAYS_VERIFIED'), ('present', 1)):
            doc = candidate()
            doc['components']['integration'][key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_non_public_or_secret_urls_are_invalid_even_if_approved(self):
        for url in ('http://synthetic-product.test/pricing', 'https://user:pass@synthetic-product.test/',
                    'https://synthetic-product.test/pricing?%74oken=TEST-NOT-SECRET',
                    'https://synthetic-product.test:444/pricing', 'https://127.0.0.1/pricing',
                    'https://private.local/pricing', 'https://synthetic-product.test/pricing#fragment'):
            with self.subTest(url=url):
                self.assertFalse(evaluate_infrastructure(candidate(), [url])['eligible'])

    def test_real_paid_price_requires_positive_finite_number_currency_cadence(self):
        for change in ({'amount': 'TODO'}, {'amount': '0'}, {'amount': '-1'}, {'amount': 'NaN'},
                       {'amount': float('inf')}, {'amount': True}, {'currency': '$'},
                       {'cadence': 'unknown'}):
            doc = candidate()
            doc['components']['pricing']['prices'][0].update(change)
            with self.subTest(change=change):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_all_supported_providers_can_qualify(self):
        for provider in ('stripe', 'paddle', 'lemonsqueezy'):
            doc = candidate()
            doc['components']['integration']['provider'] = provider
            with self.subTest(provider=provider):
                self.assertTrue(evaluate_infrastructure(doc, [PRICING])['eligible'])

    def test_shared_artifact_deduplication_no_io_and_no_mutation(self):
        doc = candidate()
        for item in (doc['current_product_context'], *doc['components'].values()):
            item['evidence_id'] = 'SAME-TEST-RECORD'
        original = copy.deepcopy(doc)
        with patch('builtins.open', side_effect=AssertionError('no file I/O')):
            result = evaluate_infrastructure(doc, [PRICING])
        self.assertEqual(result['evidence_ids'], ['SAME-TEST-RECORD'])
        self.assertEqual(doc, original)

    def test_empty_malformed_input_and_approval_types_fail_closed(self):
        for doc in (None, [], {}, {'product': 'SYNTHETIC-PRODUCT'},
                    {'product': 'SYNTHETIC-PRODUCT', 'founder': 'founder', 'current_product_context': []}):
            with self.subTest(doc=doc):
                self.assertFalse(evaluate_infrastructure(doc, [PRICING])['eligible'])
        for approvals in (None, PRICING, [None], [3]):
            with self.subTest(approvals=approvals):
                self.assertFalse(evaluate_infrastructure(candidate(), approvals)['eligible'])


if __name__ == '__main__':
    unittest.main()
