"""Offline provenance and qualification gates; synthetic cases are not evidence."""
import copy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from money_trend.core import DataError
from money_trend.live_v4_merge import _select_claims, apply_opportunity_gate, build_ledger, checked_records, score_lead


REPO = Path(__file__).resolve().parents[1]


def record():
    return {'evidence_id': 'TEST-HN01', 'source_id': '123', 'author': 'TEST-maker',
        'title': 'Show HN: SYNTHETIC-PRODUCT',
        'story_text': 'I built SYNTHETIC-PRODUCT: https://synthetic-product.test/. Someone can send coffee for USD $8 to Canada.',
        'post_text_urls': ['https://synthetic-product.test/'],
        'source_url_from_response': 'https://synthetic-product.test/',
        'url': 'https://news.ycombinator.com/item?id=123',
        'source_request_url': 'https://hn.algolia.com/api/v1/search?tags=show_hn',
        'raw_response_path': 'artifacts/live-evidence-v4/TEST-ONLY/capture.body',
        'raw_response_sha256': 'a' * 64, 'raw_locator': 'hits[0]'}


def review():
    return {'evidence_id': 'TEST-HN01', 'product': 'SYNTHETIC-PRODUCT', 'founder': 'HN TEST-maker',
        'context_quote': 'I built SYNTHETIC-PRODUCT', 'product_url': 'https://synthetic-product.test/',
        'homepage_url': 'https://synthetic-product.test/', 'pricing_quote': None,
        'scope_warning': 'SYNTHETIC non-AI coffee gifting fixture', 'gaps': []}


class LiveV4MergeTests(unittest.TestCase):
    def test_pending_price_is_zero_and_literal_non_ai_price_is_seventy(self):
        lead = review()
        result = score_lead(record(), lead)
        self.assertEqual(result['score'], 40)
        self.assertEqual(result['score_components'], {'integration': 0, 'pricing': 0, 'linkage': 40})
        lead['pricing_quote'] = 'Someone can send coffee for USD $8 to Canada.'
        result = score_lead(record(), lead)
        self.assertEqual(result['score'], 70)
        self.assertEqual(result['scope_warning'], lead['scope_warning'])
        self.assertFalse(result['integration_verified'])
        self.assertFalse(result['pricing_page_verified'])
        self.assertFalse(result['founder_identity_verified'])

    def test_provider_mention_has_discovery_points_without_integration_proof(self):
        source = record()
        source['story_text'] += ' We may integrate Stripe in future.'
        result = score_lead(source, review())
        self.assertEqual(result['score'], 70)
        self.assertEqual(result['provider_mentions'], ['stripe'])
        self.assertFalse(result['integration_verified'])
        self.assertFalse(result['checkout_executed'])

    def test_missing_quote_cross_entity_or_unobserved_url_fails_closed(self):
        for change in ({'context_quote': 'absent quote'}, {'product': 'OTHER-PRODUCT'},
                       {'founder': 'HN different-author'}, {'evidence_id': 'OTHER-ID'},
                       {'product_url': 'https://other-product.test/'},
                       {'homepage_url': 'https://synthetic-product.test/guessed'}):
            lead = {**review(), **change}
            with self.subTest(change=change), self.assertRaisesRegex(DataError, 'CRITICAL'):
                score_lead(record(), lead)

    def test_price_quote_cannot_be_from_other_row_or_discount_only(self):
        source = record()
        source['story_text'] += ' Preorder for a $200 discount off the final price.'
        for quote in ('Different product costs USD $8.', 'Preorder for a $200 discount off the final price.'):
            lead = {**review(), 'pricing_quote': quote}
            with self.subTest(quote=quote), self.assertRaisesRegex(DataError, 'CRITICAL'):
                score_lead(source, lead)

    def test_global_minimum_cannot_be_filled_by_one_qualified_product(self):
        qualified = [{'product': 'TEST-qualified', 'tier': 'T2.5a'}]
        self.assertEqual(apply_opportunity_gate([{'score': 70}], qualified), [])
        self.assertEqual(apply_opportunity_gate([{'score': 70}] + [{'score': 40}] * 8, qualified), [])
        self.assertEqual(apply_opportunity_gate([{'score': 70}] * 5, qualified, False), [])
        self.assertEqual(apply_opportunity_gate([{'score': 70}] * 5, qualified), qualified)

    def test_eight_claim_limit_keeps_highest_score_and_all_candidate_reviews(self):
        candidates = [{'evidence_id': f'TEST-HN{i:02d}', 'score': 70 if i == 9 else 40}
                      for i in range(1, 10)]
        claims = [{'evidence_id': candidate['evidence_id'], 'claim_id': 'temporary'} for candidate in candidates]
        original = copy.deepcopy(candidates)
        result = _select_claims(candidates, claims)
        self.assertEqual(len(result), 8)
        self.assertEqual([claim['evidence_id'] for claim in result],
                         ['TEST-HN09'] + [f'TEST-HN{i:02d}' for i in range(1, 8)])
        self.assertEqual([claim['claim_id'] for claim in result], [f'V4-C{i:02d}' for i in range(1, 9)])
        self.assertEqual(candidates, original)
        self.assertEqual(len(candidates), 9)

    def test_current_run_has_nine_reviews_but_only_eight_published_claims(self):
        result = build_ledger(REPO)
        self.assertEqual((result['candidate_count'], result['claim_count']), (9, 8))
        self.assertEqual(result['claim_selection']['limit'], 8)
        self.assertEqual(result['claim_selection']['selected_evidence_ids'][0], 'V4-HN22')
        self.assertEqual(result['shortlist_count'], 1)
        self.assertEqual(result['opportunities'], [])

    def test_scoring_does_not_mutate_inputs_or_open_network(self):
        source, lead = record(), review()
        original_source, original_lead = copy.deepcopy(source), copy.deepcopy(lead)
        with patch('socket.socket', side_effect=AssertionError('offline')):
            score_lead(source, lead)
        self.assertEqual(source, original_source)
        self.assertEqual(lead, original_lead)

    def capture_copy(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        target = root / 'artifacts/live-evidence-v4'
        target.mkdir(parents=True)
        shutil.copytree(REPO / 'artifacts/live-evidence-v4/scan', target / 'scan')
        shutil.copyfile(REPO / 'artifacts/live-evidence-v4/hn_evidence.jsonl', target / 'hn_evidence.jsonl')
        return root

    def test_real_capture_replays_same_ids_and_corrects_only_derived_url_labels(self):
        root = self.capture_copy()
        captured = root / 'artifacts/live-evidence-v4/hn_evidence.jsonl'
        old = captured.read_bytes()
        result = checked_records(root)
        self.assertEqual(len(result), 26)
        hanging = next(r for r in result if r['evidence_id'] == 'V4-HN05')
        self.assertIn('https://hangingcontext.com/stories/2026-11-02/agent-stack-rebuilt-from-below/', hanging['post_text_urls'])
        self.assertNotIn('https://hangingcontext.com/stories/2026-11-02/agent-stack-re', hanging['post_text_urls'])
        self.assertEqual(captured.read_bytes(), old)

    def test_changed_raw_hash_is_critical(self):
        root = self.capture_copy()
        raw = next((root / 'artifacts/live-evidence-v4/scan/requests').glob('*.body'))
        raw.write_bytes(raw.read_bytes() + b' ')
        with self.assertRaisesRegex(DataError, 'CRITICAL.*hash'):
            checked_records(root)

    def test_changed_normalized_quote_or_locator_is_critical(self):
        for needle, replacement in (('"author": "dyscrete"', '"author": "TEST-tampered"'),
                                    ('"raw_locator": "hits[0]"', '"raw_locator": "../escape"')):
            root = self.capture_copy()
            path = root / 'artifacts/live-evidence-v4/hn_evidence.jsonl'
            original = path.read_text(encoding='utf-8')
            self.assertIn(needle, original)
            path.write_text(original.replace(needle, replacement, 1), encoding='utf-8')
            with self.subTest(needle=needle), self.assertRaisesRegex(DataError, 'CRITICAL'):
                checked_records(root)


if __name__ == '__main__':
    unittest.main()
