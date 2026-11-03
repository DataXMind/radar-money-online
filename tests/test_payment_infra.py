"""Synthetic T2.5 policy fixtures only; never real payment or deployment proof."""
import copy
import unittest
from unittest.mock import patch

from money_trend.payment_infra import evaluate_infrastructure


def proof(component):
    return {'present': True, 'product': 'SYNTHETIC-PRODUCT',
            'review_status': 'CONFIRMED_SOURCE_STATEMENT',
            'observation_type': 'CURRENT_PRODUCT_DOCUMENTATION',
            'evidence_id': 'TEST-' + component,
            'source_url': 'https://api.github.com/repos/TEST/TEST/readme',
            'raw_response_path': 'artifacts/live-evidence-v2/TEST-ONLY/readme.body',
            'raw_response_sha256': 'a' * 64, 'raw_locator': 'content.decoded.' + component,
            'quote': 'SYNTHETIC current product documentation for ' + component}


def candidate():
    context = {**proof('context'), 'context': 'CURRENT_PRODUCT', 'scaffold_only': False}
    return {'product': 'SYNTHETIC-PRODUCT', 'current_product_context': context,
            'components': {'integration': {**proof('integration'), 'provider': 'stripe'},
                           'pricing': proof('pricing'), 'checkout': proof('checkout')}}


class PaymentInfrastructureTests(unittest.TestCase):
    def test_all_components_of_current_product_are_emerging_only(self):
        result = evaluate_infrastructure(candidate())
        self.assertEqual((result['tier'], result['verdict'], result['eligible']), ('T2.5', 'EMERGING', True))
        self.assertEqual(result['evidence_ids'], ['TEST-context', 'TEST-integration', 'TEST-pricing', 'TEST-checkout'])
        self.assertTrue(result['source_statement_review_only'])
        for field in ('deployed_checkout_verified', 'transaction_verified', 'checkout_executed',
                      'verified_payment', 'longitudinal_t7_t14_verified'):
            self.assertFalse(result[field])

    def test_missing_any_component_never_qualifies(self):
        for name in ('integration', 'pricing', 'checkout'):
            doc = candidate()
            del doc['components'][name]
            with self.subTest(name=name):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_present_boolean_requires_actual_review_and_trace(self):
        for field, value in (('present', False), ('present', 1), ('quote', ''), ('raw_locator', ''),
                             ('review_status', 'SOURCE_SAYS_VERIFIED'), ('raw_response_sha256', 'invalid'),
                             ('observation_type', 'FUTURE_WISHLIST'), ('observation_type', 'TEMPLATE_DEMO')):
            doc = candidate()
            doc['components']['integration'][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_cross_product_component_or_context_is_rejected(self):
        for name in ('integration', 'pricing', 'checkout', 'context'):
            doc = candidate()
            proof_to_change = doc['current_product_context'] if name == 'context' else doc['components'][name]
            proof_to_change['product'] = 'OTHER-PRODUCT'
            with self.subTest(name=name):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_template_tutorial_demo_or_unknown_context_does_not_qualify(self):
        for field, value in (('scaffold_only', True), ('scaffold_only', None), ('scaffold_only', 0),
                             ('context', 'TEMPLATE'), ('context', 'TUTORIAL'), ('context', 'DEMO')):
            doc = candidate()
            doc['current_product_context'][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])
        doc = candidate()
        del doc['current_product_context']
        self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_single_provider_mention_or_paying_customer_self_report_is_not_t25(self):
        for quote in ('Stripe', 'I have paying customers and MRR'):
            doc = {'product': 'SYNTHETIC-PRODUCT', 'quote': quote, 'metadata': ['stripe'],
                   'current_product_context': candidate()['current_product_context'],
                   'components': {'integration': {**proof('integration'), 'provider': 'stripe'}}}
            with self.subTest(quote=quote):
                result = evaluate_infrastructure(doc)
                self.assertFalse(result['eligible'])
                self.assertEqual(result['verdict'], 'RESEARCH_DRAFT_ONLY')

    def test_credentialed_external_or_insecure_source_urls_are_rejected(self):
        for url in ('http://github.com/TEST/TEST', 'https://stripe.com/pricing',
                    'https://feed.indiehackers.world/', 'https://github.com.evil.test/',
                    'https://user:pass@api.github.com/repos/TEST/TEST', 'https://github.com:444/TEST/TEST',
                    'https://api.github.com/repos/TEST/TEST?access_token=TEST-NOT-SECRET',
                    'https://api.github.com/repos/TEST/TEST?%74oken=TEST-NOT-SECRET',
                    'https://github.com/TEST/TEST#unfetched-fragment',
                    'https://api.github.com/repos/TEST/TEST?client_secret=TEST-NOT-SECRET'):
            doc = candidate()
            doc['components']['checkout']['source_url'] = url
            with self.subTest(url=url):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_raw_paths_must_stay_in_current_artifact_run(self):
        for path in ('artifacts/live-evidence-v1/old.body', '../outside.body',
                     '/artifacts/live-evidence-v2/raw.body', 'C:/secret.body',
                     'artifacts/live-evidence-v2/../other/raw.body',
                     'artifacts/live-evidence-v2', 'artifacts/live-evidence-v2evil/raw.body'):
            doc = candidate()
            doc['components']['checkout']['raw_response_path'] = path
            with self.subTest(path=path):
                self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_supported_providers_and_current_implementation_are_allowed(self):
        for provider in ('stripe', 'paddle', 'lemonsqueezy'):
            doc = candidate()
            doc['components']['integration']['provider'] = provider
            doc['components']['checkout']['observation_type'] = 'CURRENT_PRODUCT_IMPLEMENTATION'
            with self.subTest(provider=provider):
                self.assertTrue(evaluate_infrastructure(doc)['eligible'])
        doc = candidate()
        doc['components']['integration']['provider'] = 'other'
        self.assertFalse(evaluate_infrastructure(doc)['eligible'])

    def test_provider_linkage_cannot_join_different_billing_stacks(self):
        doc = candidate()
        doc['components']['checkout']['provider'] = 'paddle'
        result = evaluate_infrastructure(doc)
        self.assertFalse(result['eligible'])
        self.assertIn('CROSS_PROVIDER_COMPONENT_LINKAGE', result['reasons'])

    def test_empty_or_malformed_candidates_are_draft_not_hyped(self):
        for value in (None, [], {}, {'product': ''}, {'product': 'TEST', 'current_product_context': []}):
            with self.subTest(value=value):
                result = evaluate_infrastructure(value)
                self.assertIsNone(result['tier'])
                self.assertEqual(result['verdict'], 'RESEARCH_DRAFT_ONLY')
                self.assertFalse(result['eligible'])

    def test_shared_artifact_is_not_counted_as_independent_evidence(self):
        doc = candidate()
        for item in (doc['current_product_context'], *doc['components'].values()):
            item['evidence_id'] = 'SAME-TEST-RECORD'
        result = evaluate_infrastructure(doc)
        self.assertTrue(result['eligible'])
        self.assertEqual(result['evidence_ids'], ['SAME-TEST-RECORD'])

    def test_no_io_and_no_input_mutation(self):
        doc = candidate()
        original = copy.deepcopy(doc)
        with patch('builtins.open', side_effect=AssertionError('no file I/O')):
            self.assertTrue(evaluate_infrastructure(doc)['eligible'])
        self.assertEqual(doc, original)

    def test_missing_source_evidence_id_uses_explicit_raw_locator_reference(self):
        doc = candidate()
        for item in (doc['current_product_context'], *doc['components'].values()):
            del item['evidence_id']
        result = evaluate_infrastructure(doc)
        self.assertTrue(result['eligible'])
        self.assertTrue(all(ref.startswith('artifacts/live-evidence-v2/TEST-ONLY/readme.body#')
                            for ref in result['evidence_ids']))
