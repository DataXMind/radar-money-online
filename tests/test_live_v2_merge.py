"""Offline v2 trace checks; actual archives are read only, positives synthetic."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError
from money_trend import live_v2_merge as merge

ROOT = Path(__file__).resolve().parents[1]


class LiveV2MergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gh = merge.jsonl(ROOT / merge.OUT / 'github_evidence.jsonl')
        cls.hn = merge.jsonl(ROOT / merge.OUT / 'hn_evidence.jsonl')
        cls.records = cls.gh + cls.hn
        cls.components = json.loads((ROOT / merge.OUT / 'component_review.json').read_text(encoding='utf-8'))
        cls.review = merge.make_review(ROOT, cls.components)

    def test_actual_fifteen_records_eight_claims_zero_opportunities_and_separate_baseline(self):
        ledger = merge.build_ledger(ROOT, self.review)
        self.assertEqual((ledger['raw_count'], ledger['claim_count'], ledger['opportunity_count']), (15, 8, 0))
        self.assertEqual(ledger['source_counts'], {'github': 8, 'hn': 7})
        self.assertEqual(ledger['request_counts'], {'ws1': 12, 'ws2': 6})
        self.assertEqual(ledger['status'], 'RESEARCH_DRAFT_ONLY')
        self.assertEqual(len(ledger['responses']), 18)
        self.assertFalse(ledger['baseline']['merged'])
        self.assertEqual(ledger['baseline']['records'], 15)
        self.assertFalse(ledger['baseline']['t7_executed'])
        self.assertEqual(len(ledger['raw_items']), 15)  # Baseline is never appended.
        self.assertTrue(all(row['tier'] == 'T3' and not row['eligible'] for row in ledger['evaluations']))

    def test_every_actual_record_and_selected_quote_resolves_to_raw(self):
        for item in self.records:
            with self.subTest(evidence_id=item['evidence_id']):
                merge.checked_record(ROOT, item)
        for claim in self.review['claims']:
            value = merge.checked_quote(ROOT, claim)
            self.assertIn(claim['quote'], value)

    def test_record_hash_path_locator_and_readme_line_tampering_rejected(self):
        for field, value in [('raw_response_sha256', '0' * 64),
                             ('raw_response_path', 'artifacts/mvp-v1/evidence_ledger.json'),
                             ('raw_locator', 'items[99999]'), ('repo', 'OTHER/PRODUCT')]:
            item = copy.deepcopy(self.gh[0])
            item[field] = value
            with self.subTest(field=field), self.assertRaises(DataError):
                merge.checked_record(ROOT, item)
        item = copy.deepcopy(self.gh[0])
        item['readme']['component_signals']['pricing']['quotes'][0]['decoded_readme_line'] = 99999
        with self.assertRaisesRegex(DataError, 'README identity/blob/excerpt/signals'):
            merge.checked_record(ROOT, item)

    def test_hn_content_and_time_must_equal_captured_raw(self):
        for field, value in [('content_excerpt', 'SYNTHETIC NOT IN ACTUAL SOURCE'),
                             ('created_at_i', 1), ('author', 'OTHER-FOUNDER')]:
            item = copy.deepcopy(self.hn[0])
            item[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(DataError, 'HN normalized fields'):
                merge.checked_record(ROOT, item)

    def test_quote_must_be_on_exact_readme_line_not_elsewhere_in_document(self):
        proof = copy.deepcopy(self.review['claims'][0])
        for field, value in [('raw_locator', 'decoded_readme.lines[999999]'),
                             ('raw_locator', 'decoded_readme.lines[0]'),
                             ('quote', 'SYNTHETIC ABSENT QUOTE'),
                             ('raw_response_sha256', '0' * 64)]:
            altered = {**proof, field: value}
            with self.subTest(field=field, value=value), self.assertRaises(DataError):
                merge.checked_quote(ROOT, altered)

    def test_cross_product_components_and_repository_identity_rejected(self):
        for target in ('candidate', 'component'):
            review = copy.deepcopy(self.review)
            if target == 'candidate':
                review['candidates'][0]['product'] = 'OTHER/PRODUCT'
            else:
                review['candidates'][0]['infrastructure']['components']['integration']['product'] = 'OTHER/PRODUCT'
            with self.subTest(target=target), self.assertRaises(DataError):
                merge.evaluate_review(ROOT, self.records, review)

    def test_valid_quote_from_other_readme_cannot_support_wrong_claim_id(self):
        review = copy.deepcopy(self.review)
        replacement = review['claims'][1]
        self.assertNotEqual(review['claims'][0]['evidence_id'], replacement['evidence_id'])
        for key in ('source_url', 'raw_response_path', 'raw_response_sha256', 'raw_locator', 'quote'):
            review['claims'][0][key] = replacement[key]
        # The substituted quote itself is real and valid, but belongs to GH03.
        merge.checked_quote(ROOT, review['claims'][0])
        with self.assertRaisesRegex(DataError, 'provenance does not belong'):
            merge.evaluate_review(ROOT, self.records, review)

    def test_valid_other_repo_readme_cannot_support_current_product_component(self):
        review = copy.deepcopy(self.review)
        proof = review['candidates'][0]['infrastructure']['components']['integration']
        replacement = review['claims'][1]
        for key in ('source_url', 'raw_response_path', 'raw_response_sha256', 'raw_locator', 'quote'):
            proof[key] = replacement[key]
        self.assertEqual(proof['evidence_id'], review['candidates'][0]['evidence_id'])
        merge.checked_quote(ROOT, proof)
        with self.assertRaisesRegex(DataError, 'provenance does not belong'):
            merge.evaluate_review(ROOT, self.records, review)

    def test_claim_budget_and_missing_economic_field_mapping_rejected(self):
        review = copy.deepcopy(self.review)
        review['claims'].append(copy.deepcopy(review['claims'][0]))
        with self.assertRaisesRegex(DataError, 'claim budget'):
            merge.evaluate_review(ROOT, self.records, review)
        review = copy.deepcopy(self.review)
        proof = copy.deepcopy(review['claims'][0])
        proof.update(product=review['candidates'][0]['product'], founder='SYNTHETIC', metric='MRR',
                     currency='USD', cadence='monthly', value='1', period_start='2026-01-01',
                     period_end='2026-01-31', observed_at='2026-02-01T00:00:00Z')
        review['candidates'][0]['transaction_or_history']['points'] = [proof]
        with self.assertRaisesRegex(DataError, 'economic field mapping'):
            merge.evaluate_review(ROOT, self.records, review)

    def test_baseline_hash_mutation_is_rejected_using_temporary_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shutil.copytree(ROOT / 'artifacts', root / 'artifacts')
            path = root / 'artifacts/t7-baseline/snapshot_t0.jsonl'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(DataError, 'baseline changed'):
                merge.build_ledger(root, self.review)

    def test_synthetic_complete_t25_is_emerging_not_payment_and_top_five_only(self):
        """Pure merge policy test; quote verifier mocked, not actual proof coverage."""
        records, candidates = [], []
        for index in range(6):
            ident, product = f'SYNTHETIC-{index}', f'TEST-PRODUCT-{index}'
            records.append({'evidence_id': ident, 'source': 'hn', 'url': 'https://hn.algolia.com/api/v1/items/1'})
            proof = {'present': True, 'product': product, 'review_status': 'CONFIRMED_SOURCE_STATEMENT',
                     'observation_type': 'CURRENT_PRODUCT_DOCUMENTATION', 'evidence_id': ident,
                     'source_url': 'https://hn.algolia.com/api/v1/items/1',
                     'raw_response_path': 'artifacts/live-evidence-v2/ws2/requests/SYNTHETIC.body',
                     'raw_response_sha256': 'a' * 64, 'raw_locator': 'hits[0].comment_text',
                     'quote': 'SYNTHETIC ONLY, not a captured real statement'}
            records[-1].update(source_request_url=proof['source_url'],
                               raw_response_path=proof['raw_response_path'],
                               raw_response_sha256=proof['raw_response_sha256'], raw_locator='hits[0]')
            infra = {'product': product,
                     'current_product_context': {**proof, 'context': 'CURRENT_PRODUCT', 'scaffold_only': False},
                     'components': {'integration': {**proof, 'provider': 'stripe'},
                                    'pricing': dict(proof), 'checkout': dict(proof)}}
            candidates.append({'evidence_id': ident, 'product': product, 'infrastructure': infra,
                               'transaction_or_history': {'product': product, 'points': []}})
        with patch.object(merge, 'checked_quote', return_value='SYNTHETIC ONLY'):
            result = merge.evaluate_review(ROOT, records, {'candidates': candidates, 'claims': []})
        self.assertEqual(len(result['evaluations']), 6)
        self.assertEqual(len(result['opportunities']), 5)
        for opp in result['opportunities']:
            self.assertEqual((opp['tier'], opp['verdict']), ('T2.5', 'EMERGING'))
            self.assertFalse(opp['verified_payment'])
            self.assertFalse(opp['payment_evidence']['present'])
            self.assertFalse(opp['buyer_evidence']['present'])
            self.assertFalse(opp['trend_evidence']['present'])
            self.assertFalse(opp['deployed_checkout_verified'])
            self.assertFalse(opp['checkout_executed'])
