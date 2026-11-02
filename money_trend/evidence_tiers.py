"""Pure classification of caller-reviewed source observations; no I/O or requests.

The caller must verify raw hashes, locators, quotes and entity/value mappings.
CONFIRMED_SOURCE_STATEMENT attests that the source said it, not that it is true.
This run accepts source_url only on feed.indiehackers.world.
"""
import calendar
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePosixPath
from urllib.parse import urlsplit

HOST = 'feed.indiehackers.world'
REVIEW = 'CONFIRMED_SOURCE_STATEMENT'
META_KINDS = {'repo_star', 'hn_points', 'comment', 'post_metadata', 'publication_metadata'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _source_url(value):
    if not _text(value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname == HOST and not url.username
                and not url.password and url.port in (None, 443) and not url.fragment)
    except ValueError:
        return False


def _trace(proof):
    if not isinstance(proof, dict) or not _text(proof.get('raw_response_path')):
        return False
    path = PurePosixPath(proof['raw_response_path'].replace('\\', '/'))
    return (proof.get('review_status') == REVIEW
            and _text(proof.get('evidence_id')) and _source_url(proof.get('source_url'))
            and not path.is_absolute() and path.parts[0] == 'artifacts'
            and '..' not in path.parts and ':' not in str(path)
            and isinstance(proof.get('raw_response_sha256'), str)
            and bool(re.fullmatch(r'[a-f0-9]{64}', proof['raw_response_sha256']))
            and _text(proof.get('raw_locator')) and _text(proof.get('quote')))


def _timestamp(value):
    if not _text(value):
        raise ValueError('timezone-aware timestamp required')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone-aware timestamp required')
    return result


def _period(point):
    start, end = date.fromisoformat(point['period_start']), date.fromisoformat(point['period_end'])
    cadence = point['cadence']
    if start > end or end > _timestamp(point['observed_at']).date():
        raise ValueError('invalid/future reporting period')
    observation_type = point.get('observation_type', 'period')
    if observation_type == 'snapshot':
        if point['metric'] != 'MRR' or cadence != 'monthly' or start != end:
            raise ValueError('MRR snapshot requires one explicit date and monthly cadence')
        return start, end
    if observation_type != 'period':
        raise ValueError('unsupported observation type')
    if cadence == 'monthly':
        valid = (start.day == 1 and start.year == end.year and start.month == end.month
                 and end.day == calendar.monthrange(start.year, start.month)[1])
    elif cadence == 'quarterly':
        valid = (start.day == 1 and start.month in (1, 4, 7, 10) and start.year == end.year
                 and end.month == start.month + 2 and end.day == calendar.monthrange(end.year, end.month)[1])
    elif cadence == 'annual':
        valid = start.month == start.day == 1 and end == date(start.year, 12, 31)
    elif cadence == 'weekly':
        valid = (end - start).days == 6
    else:
        valid = False
    if not valid or (point['metric'] == 'MRR' and cadence != 'monthly'):
        raise ValueError('invalid/inconsistent cadence')
    return start, end


def _value(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('numeric source value required')
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('invalid source value') from exc
    if not number.is_finite() or number < 0:
        raise ValueError('invalid source value')


def _t2(candidate):
    points = candidate.get('points')
    if not isinstance(points, list) or len(points) < 3:
        return [], ['T2_REQUIRES_AT_LEAST_THREE_POINTS']
    if len(points) > 120:
        return [], ['T2_POINT_BUDGET_EXCEEDED']
    if not _text(candidate.get('product')) or not _text(candidate.get('founder')):
        return [], ['T2_PRODUCT_AND_FOUNDER_REQUIRED']
    periods, signatures, reasons = [], set(), []
    for index, point in enumerate(points):
        try:
            if (not _trace(point) or point.get('actual') is not True
                    or point.get('statement_type') != 'actual_revenue_report'
                    or point.get('product') != candidate['product']
                    or point.get('founder') != candidate['founder']
                    or point.get('metric') not in ('MRR', 'REVENUE')
                    or not isinstance(point.get('currency'), str)
                    or not re.fullmatch(r'[A-Z]{3}', point['currency'])):
                raise ValueError('unsupported/unreviewed/inconsistent statement')
            start, end = _period(point)
            _value(point.get('value'))
            signatures.add((point['metric'], point['currency'], point['cadence'],
                            point.get('observation_type', 'period')))
            periods.append((start, end, point))
        except (ValueError, TypeError, KeyError, OverflowError):
            reasons.append(f'T2_INVALID_POINT:{index}')
    if reasons:
        return [], reasons
    if len(signatures) != 1:
        return [], ['T2_MIXED_METRIC_CURRENCY_OR_CADENCE']
    periods.sort(key=lambda item: item[0])
    if any(after[0] <= before[1] for before, after in zip(periods, periods[1:])):
        return [], ['T2_DUPLICATED_OR_OVERLAPPING_PERIODS']
    if periods[0][2].get('observation_type', 'period') == 'snapshot':
        months = {(start.year, start.month) for start, _, _ in periods}
        if len(months) != len(periods):
            return [], ['T2_DUPLICATED_SNAPSHOT_MONTHS']
    # Consistent entity/definition is required; monotonic growth is not.
    return [item[2] for item in periods], []


def _t1(candidate):
    proof = candidate.get('t1_proof')
    if not isinstance(proof, dict):
        return None
    try:
        valid = (_trace(proof) and proof.get('verification_status') == 'VERIFIED_PAYMENT'
                 and proof.get('proof_type') in ('receipt', 'invoice', 'contract', 'public_filing')
                 and proof.get('payment_status') == 'PAID'
                 and proof.get('product') == candidate.get('product') and _text(proof.get('product'))
                 and _text(proof.get('buyer')) and _text(proof.get('reviewer'))
                 and proof.get('authenticity_verified') is True
                 and proof.get('buyer_product_time_linkage_verified') is True)
        _timestamp(proof.get('transaction_at'))
        _timestamp(proof.get('reviewed_at'))
        return proof if valid else None
    except (ValueError, TypeError, OverflowError):
        return None


def evaluate_candidate(candidate):
    """T1/PROVEN, T2/EMERGING, T3/HYPED or no tier.

    eligible means this transactional RSS run's Top Opportunities (T1/T2 only).
    Summary booleans or source instructions never replace upstream review.
    """
    base = {'tier': None, 'verdict': 'RESEARCH_DRAFT_ONLY', 'eligible': False,
            'reasons': [], 'evidence_ids': [], 'verified_payment': False,
            'longitudinal_t7_t14_verified': False, 'source_statement_review_only': True}
    if not isinstance(candidate, dict):
        return {**base, 'reasons': ['INVALID_CANDIDATE']}
    proof = _t1(candidate)
    if proof:
        return {**base, 'tier': 'T1', 'verdict': 'PROVEN', 'eligible': True,
                'reasons': ['REVIEWED_AUTHENTIC_PAYMENT_WITH_BUYER_PRODUCT_TIME_LINKAGE'],
                'evidence_ids': [proof['evidence_id']], 'verified_payment': True}
    points, reasons = _t2(candidate)
    if points:
        return {**base, 'tier': 'T2', 'verdict': 'EMERGING', 'eligible': True,
                'reasons': ['AT_LEAST_THREE_REVIEWED_SELF_REPORTED_REVENUE_PERIODS',
                            'SELF_REPORTED_NOT_VERIFIED_PAYMENT', 'NOT_A_PROSPECTIVE_T7_T14_MEASUREMENT'],
                'evidence_ids': list(dict.fromkeys(point['evidence_id'] for point in points)),
                'history_points': len(points)}
    metadata = candidate.get('metadata', [])
    if isinstance(metadata, list):
        valid_meta = [item for item in metadata if isinstance(item, dict)
                      and item.get('kind') in META_KINDS and _trace(item)]
        if valid_meta:
            return {**base, 'tier': 'T3', 'verdict': 'HYPED', 'eligible': False,
                    'reasons': reasons + ['METADATA_ONLY_NOT_TRANSACTIONAL_OPPORTUNITY'],
                    'evidence_ids': list(dict.fromkeys(item['evidence_id'] for item in valid_meta))}
    return {**base, 'reasons': reasons + ['NO_QUALIFYING_TIER']}
