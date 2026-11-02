# AI Money-Trend — Production v1 draft dashboard

Run: {run_id} | Generated: {generated_at}
EXECUTION_MODE: HUMAN_APPROVAL_REQUIRED | Option: B | Network: disabled

Status: **{status}**

| Overview | Count |
|---|---:|
| Retained raw records | {raw_count} |
| Metadata claims | {claim_count} |
| Qualified opportunities | {opportunity_count} |

## Verdict distribution (claims, not market classifications)

| Verdict | Count |
|---|---:|
| OBSERVED_METADATA | {claim_count} |
| HYPED | 0 |
| EMERGING | 0 |

Metadata alone cannot establish EMERGING or Top 5 eligibility. HYPED is an
upper bound for metadata, not an automatic classification.

## Top Opportunities

| Opportunity | Buyer proof | Payment proof | Trend proof |
|---|---|---|---|
{top_rows}

## GAP summary

{gap_summary}

Window: last 7 days of response retrieval, not story publication or proven growth.
Original retrieval timestamps remain in evidence_ledger.json. This is an offline
replay of archived public GitHub/HN responses, never a new live observation.
Review run_manifest.json and opportunities.csv. Not production-ready.
