"""Synthetic policy fixtures only; none represent actual source/payment proof."""
import copy
import unittest

from money_trend.evidence_tiers import V2_HOSTS, evaluate_candidate


def trace(eid='TEST01'):
    return {'evidence_id': eid, 'source_url': 'https://feed.indiehackers.world/',
            'raw_response_path': 'artifacts/TEST-ONLY/feed.body', 'raw_response_sha256': 'a' * 64,
            'raw_locator': 'channel/item[1]/description', 'quote': 'SYNTHETIC TEST ONLY',
            'review_status': 'CONFIRMED_SOURCE_STATEMENT'}


def candidate():
    points = []
    for index, (start, end, value) in enumerate((('2026-07-01', '2026-07-31', '300'),
                                               ('2026-08-01', '2026-08-31', '200'),
                                               ('2026-09-01', '2026-09-30', '250')), 1):
        points.append({**trace(f'TEST{index}'), 'product': 'TEST-PRODUCT', 'founder': 'TEST-FOUNDER',
                       'metric': 'MRR', 'currency': 'USD', 'cadence': 'monthly', 'value': value,
                       'period_start': start, 'period_end': end, 'observed_at': '2026-10-02T00:00:00Z',
                       'actual': True, 'statement_type': 'actual_revenue_report'})
    return {'product': 'TEST-PRODUCT', 'founder': 'TEST-FOUNDER', 'points': points}


class EvidenceTierTests(unittest.TestCase):
    def test_three_periods_are_emerging_even_when_revenue_falls(self):
        r = evaluate_candidate(candidate())
        self.assertEqual((r['tier'], r['verdict'], r['eligible']), ('T2', 'EMERGING', True))
        self.assertFalse(r['verified_payment'])
        self.assertFalse(r['longitudinal_t7_t14_verified'])
        self.assertEqual(r['history_points'], 3)

    def test_two_points_are_not_t2(self):
        doc = candidate(); doc['points'].pop()
        self.assertFalse(evaluate_candidate(doc)['eligible'])

    def test_three_explicit_monthly_mrr_snapshots_are_emerging(self):
        doc = candidate()
        for point, day in zip(doc['points'], ('2026-07-10', '2026-08-03', '2026-09-21')):
            point.update(observation_type='snapshot', period_start=day, period_end=day)
        result = evaluate_candidate(doc)
        self.assertEqual((result['tier'], result['verdict']), ('T2', 'EMERGING'))
        self.assertEqual(result['history_points'], 3)
        self.assertFalse(result['verified_payment'])

    def test_same_month_snapshots_are_not_three_monthly_reports(self):
        doc = candidate()
        for point, day in zip(doc['points'], ('2026-07-01', '2026-07-10', '2026-07-20')):
            point.update(observation_type='snapshot', period_start=day, period_end=day)
        result = evaluate_candidate(doc)
        self.assertFalse(result['eligible'])
        self.assertIn('T2_DUPLICATED_SNAPSHOT_MONTHS', result['reasons'])

    def test_mixed_snapshot_and_period_or_invalid_snapshot_rejected(self):
        for update in ({'observation_type': 'snapshot', 'period_end': '2026-07-01'},
                       {'observation_type': 'snapshot'},
                       {'observation_type': 'estimated'}):
            doc = candidate()
            doc['points'][0].update(update)
            with self.subTest(update=update):
                self.assertFalse(evaluate_candidate(doc)['eligible'])

    def test_duplicate_reposts_or_periods_do_not_count(self):
        for eid in ('TEST1', 'DIFFERENT-REPOST'):
            doc = candidate(); doc['points'][2] = {**doc['points'][0], 'evidence_id': eid}
            self.assertIn('T2_DUPLICATED_OR_OVERLAPPING_PERIODS', evaluate_candidate(doc)['reasons'])

    def test_identity_metric_currency_cadence_mixing_rejected(self):
        for field, value in [('product', 'OTHER'), ('founder', 'OTHER'), ('metric', 'REVENUE'),
                             ('metric', 'ARR'), ('currency', 'EUR'), ('cadence', 'weekly')]:
            doc = candidate(); doc['points'][1][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(evaluate_candidate(doc)['eligible'])

    def test_prices_forecasts_goals_or_unreviewed_points_rejected(self):
        for field, value in [('actual', False), ('statement_type', 'forecast'), ('statement_type', 'pricing'),
                             ('statement_type', 'goal'), ('review_status', 'SOURCE_SAYS_VERIFIED')]:
            doc = candidate(); doc['points'][0][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(evaluate_candidate(doc)['eligible'])

    def test_invalid_periods_timestamps_values_and_trace_rejected(self):
        for field, value in [('period_end', '2026-07-32'), ('period_end', '2026-08-31'),
                             ('period_end', '2027-07-31'), ('observed_at', '2026-10-02'),
                             ('value', True), ('value', 'NaN'), ('value', '-1'),
                             ('raw_response_path', '../secrets'), ('raw_response_sha256', 'bad'),
                             ('source_url', 'https://indiehackers.com/post'),
                             ('source_url', 'https://feed.indiehackers.world.evil.test/')]:
            doc = candidate(); doc['points'][0][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(evaluate_candidate(doc)['eligible'])

    def test_one_post_may_explicitly_report_three_different_periods(self):
        doc = candidate()
        for point in doc['points']:
            point['evidence_id'] = 'SINGLE-POST-WITH-THREE-PERIODS'
        r = evaluate_candidate(doc)
        self.assertEqual(r['tier'], 'T2')
        self.assertEqual(r['evidence_ids'], ['SINGLE-POST-WITH-THREE-PERIODS'])
        self.assertFalse(r['verified_payment'])

    def test_metadata_hyped_not_transactional_opportunity(self):
        r = evaluate_candidate({'metadata': [{**trace(), 'kind': 'post_metadata'}]})
        self.assertEqual((r['tier'], r['verdict'], r['eligible']), ('T3', 'HYPED', False))

    def test_unverified_metadata_does_not_create_tier(self):
        r = evaluate_candidate({'metadata': [{'kind': 'comment', 'evidence_id': 'NO-TRACE'}]})
        self.assertIsNone(r['tier'])
        self.assertFalse(r['eligible'])

    def test_verified_boolean_or_self_report_never_becomes_t1(self):
        doc = candidate(); doc['t1_proof'] = {**trace(), 'verified': True, 'proof_type': 'receipt'}
        self.assertEqual(evaluate_candidate(doc)['tier'], 'T2')
        self.assertFalse(evaluate_candidate(doc)['verified_payment'])

    def test_t1_requires_paid_authentic_transaction_and_linkage(self):
        doc = candidate()
        proof = {**trace('TEST-PAID'), 'proof_type': 'receipt', 'verification_status': 'VERIFIED_PAYMENT',
                 'payment_status': 'PAID', 'product': doc['product'], 'buyer': 'TEST-BUYER',
                 'reviewer': 'TEST-REVIEWER', 'authenticity_verified': True,
                 'buyer_product_time_linkage_verified': True, 'transaction_at': '2026-10-01T00:00:00Z',
                 'reviewed_at': '2026-10-02T00:00:00Z'}
        doc['t1_proof'] = proof
        self.assertEqual(evaluate_candidate(doc)['verdict'], 'PROVEN')
        self.assertTrue(evaluate_candidate(doc)['verified_payment'])
        for field, value in [('payment_status', 'INVOICED'), ('buyer_product_time_linkage_verified', False),
                             ('authenticity_verified', False), ('product', 'OTHER')]:
            modified = copy.deepcopy(doc); modified['t1_proof'][field] = value
            with self.subTest(field=field):
                self.assertNotEqual(evaluate_candidate(modified)['tier'], 'T1')

    def test_no_evidence_is_draft(self):
        for value in ({}, None, [], 'source instructions'):
            with self.subTest(value=value):
                r = evaluate_candidate(value)
                self.assertIsNone(r['tier'])
                self.assertFalse(r['eligible'])

    def test_v2_explicit_hn_scope_accepts_three_reviewed_periods_only_as_self_report(self):
        doc = candidate()
        for point in doc['points']:
            point['source_url'] = 'https://hn.algolia.com/api/v1/items/123'
        result = evaluate_candidate(doc, allowed_hosts=V2_HOSTS)
        self.assertEqual((result['tier'], result['verdict']), ('T2', 'EMERGING'))
        self.assertFalse(result['verified_payment'])
        self.assertFalse(result['longitudinal_t7_t14_verified'])
        self.assertIsNone(evaluate_candidate(doc)['tier'])

    def test_v2_scope_excludes_disabled_rss_host(self):
        self.assertIsNone(evaluate_candidate(candidate(), allowed_hosts=V2_HOSTS)['tier'])
        self.assertEqual(evaluate_candidate(candidate())['tier'], 'T2')

    def test_unknown_or_empty_scopes_fail_closed(self):
        for scope in (None, (), [], set(), 'hn.algolia.com', {'example.com'},
                      {'hn.algolia.com', 'example.com'}, [None], [True]):
            with self.subTest(scope=scope):
                result = evaluate_candidate(candidate(), allowed_hosts=scope)
                self.assertIsNone(result['tier'])
                self.assertFalse(result['eligible'])
                self.assertEqual(result['reasons'], ['INVALID_SOURCE_SCOPE'])

    def test_v2_credentialed_or_token_urls_never_become_t2(self):
        for url in ('https://name:pass@hn.algolia.com/api/v1/items/123',
                    'https://hn.algolia.com/api/v1/items/123?token=SYNTHETIC',
                    'https://api.github.com/repos/test/test?client_secret=SYNTHETIC',
                    'https://github.com/test/test?API_KEY=SYNTHETIC',
                    'https://hn.algolia.com:8443/api/v1/items/123',
                    'http://hn.algolia.com/api/v1/items/123',
                    'https://hn.algolia.com.evil.invalid/api/v1/items/123'):
            doc = candidate()
            for point in doc['points']:
                point['source_url'] = url
            with self.subTest(url=url):
                self.assertFalse(evaluate_candidate(doc, allowed_hosts=V2_HOSTS)['eligible'])

    def test_t1_trace_respects_the_explicit_scope_without_weakening_payment_review(self):
        proof = {**trace('TEST-T1-HN'), 'source_url': 'https://api.github.com/repos/test/test/readme',
                 'proof_type': 'receipt', 'verification_status': 'VERIFIED_PAYMENT',
                 'payment_status': 'PAID', 'product': 'TEST-PRODUCT', 'buyer': 'TEST-BUYER',
                 'reviewer': 'TEST-REVIEWER', 'authenticity_verified': True,
                 'buyer_product_time_linkage_verified': True, 'transaction_at': '2026-10-01T00:00:00Z',
                 'reviewed_at': '2026-10-02T00:00:00Z'}
        doc = {'product': 'TEST-PRODUCT', 't1_proof': proof}
        self.assertEqual(evaluate_candidate(doc, allowed_hosts=V2_HOSTS)['tier'], 'T1')
        self.assertIsNone(evaluate_candidate(doc)['tier'])
        proof['authenticity_verified'] = False
        self.assertIsNone(evaluate_candidate(doc, allowed_hosts=V2_HOSTS)['tier'])
