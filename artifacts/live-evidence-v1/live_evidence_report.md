# Live evidence run v1 — parallel, draft-only

**Verdict: RESEARCH_DRAFT_ONLY. Top Opportunities: 0.**

One bounded live acquisition was performed by two scouts with an overlapping
third local trend workstream. The initial three subagents were spawned in
parallel. This is a real source fetch, unlike the prior offline baseline; it
does not establish business qualification or production readiness.

## Actual scope and counts

| Workstream | Actual result |
|---|---|
| WS-1 GitHub | 6 anonymous api.github.com GETs, all HTTP 200; 15 returned hits, 14 unique issues after one duplicate |
| WS-2 HN Algolia | 6 successful HTTP 200 GETs after 2 sandbox DNS failures; 15 returned/retained stories/comments |
| WS-3 Trend | 15 historical MVP T0 records, references to 8 historical claims; no new time-series observation |
| Merged live evidence | 29 unique records, separate from the 15 historical T0 records |
| Current claims | 8 bounded, source-attributed statements; not verified business facts |
| Research hypotheses reviewed | 6, none eligible for Top 5 |
| Opportunities | 0; CSV contains only its header |
| Offline tests | 89 PASS, 0 failures, 0 errors; socket creation blocked in the test runner |

The current instruction's 10–15 acquisition records per scout supersedes the
earlier 15-total acquisition cap for this run only. It permits at most 30 new
records; the merged claim cap remains 8 and Top 5 remains at most 5. No unrelated
records were fetched to backfill duplicates or satisfy a quota.

Actual request hosts: **api.github.com, hn.algolia.com only**. github.com issue
URLs came from GitHub responses. Canonical news.ycombinator.com item links are
derived display references from IDs, explicitly marked not fetched; this domain
was never requested. External URLs in source text are DATA, not approved fetches.

## Protocol and failures

Both scouts froze six queries before fetching. Each used per-query response
caps 3/3/3/2/2/2. GitHub selected first-page issues by updated descending; HN
selected first-page stories/comments by newest, within the frozen 30-day window
**2026-10-03 05:07:34 UTC through 2026-11-02 05:07:34 UTC**. Protocol files contain
the full query URLs, dedupe method, anchor and constraints.

GitHub capture ran approximately 12:07:33–12:08:09 Asia/Saigon. HN work began
at 12:07:34 and finished at 12:08:26, including the initial DNS failure and one
resume under network escalation. The frozen URLs/time window were unchanged.
All 14 attempts are logged: 12 successful HTTP responses and 2 DNS failures,
not 14 successful requests or 14 separate live runs. No redirect was followed.

GitHub discussions were not fetched: the implementation uses anonymous REST
issue search, without authenticated GraphQL or credentials. Several broad
queries returned noisy coordination threads or unrelated HN topics. They were
retained as search results and flagged, not counted as confirmed buyer relevance.
HN's keyword-return behavior did not ensure all query terms described the post's
actual problem; no market prevalence or representative demand statistic follows.

All three subagents later hit the runtime account usage limit. WS1/WS2 had
already saved their complete capture outputs. No worker was restarted and no
credits were purchased; the orchestrator verified saved records and finalized
WS3/merge/report locally. This operational interruption is a recorded GAP, not
a successful clean completion claim for all three model workers. No data-integrity
or unauthorized-egress CRITICAL was detected in the saved request evidence.

## What the evidence supports

Eight claims were selected after reviewing the bounded sample, to cover cost,
permissions, incidents and maker/workflow leads. This purposive selection is
disclosed; it is not a predeclared market-frequency estimate. Every claim has
an exact raw-field locator, body hash, evidence ID and attribution limitation.

| Claim / evidence | Supported observation | Qualification limit |
|---|---|---|
| L01 / GH07 | A Codex issue requests richer quota/reset/balance visibility | Requester is not a verified buyer; no transaction proof |
| L02 / GH08 | A Codex issue author alleges unexpectedly fast quota depletion | Allegation, not measured depletion or verified willingness to pay |
| L03 / GH10 | A source reports browser access/approval recovery trouble | Incident and root cause are not independently verified |
| L04 / GH12 | A source alleges headless-browser-related identity lockouts | No independently verified incident, buyer or purchase |
| L05 / GH13 | A source alleges fast weekly quota consumption on an Ultra plan | Plan/payment claim is self-report; no authenticated receipt |
| L06 / HN05 | A commenter criticizes the coding-agent user interface | Opinion, not a verified buying signal |
| L07 / HN10 | A maker describes a least-privilege agent data-access tool | Maker description is not buyer/payment proof |
| L08 / HN11 | A commenter describes an understaffed internal support workflow | Claimed company/workflow linkage remains unverified |

Source links, excerpts, authors, event/retrieval times and exact fields are in
the two scout JSONL files. Claims quote only bounded source text, not endorsed
instructions or independently established product/pricing facts. No source
instructions, diagnostic commands or external links were executed.

## Evidence gates and GAP summary

- **BUYER:** Public handles, comments, maker descriptions and paid-plan claims
  do not verify buyer identity + product + time with qualifying evidence.
- **PAYMENT:** No receipt/invoice/contract/public filing satisfying entity linkage
  and verification was established. Price mentions and claimed subscriptions
  were not promoted to transaction proof. No revenue number is inferred.
- **TREND:** **Thiếu longitudinal trend evidence — chỉ có 1 snapshot.** The user
  confirmed the 12 Cổng 2 cases were lost with an old cloud session and are not
  available here. Final WS3 uses the existing MVP only; T+7/T+14 remain null.
- **METRIC COVERAGE:** Original normalized GitHub repo records have no stored
  numeric trend metric; no historical stars/replies were reconstructed. Only
  the five original HN records retain their actual points/comments.
- **SOURCE COVERAGE/QUALITY:** No discussions capture, and broad-query noise
  limits relevance. Extra domains or new backfill queries were not used.
- **RUNTIME:** Subagent account quota interrupted final handoff; root completed
  review from persisted artifacts without retrying model delegation.

NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE and NO_LONGITUDINAL_TREND_EVIDENCE remain.
All six hypotheses explicitly mark buyer/payment/trend present=false and are
excluded. Having more records or a high comment count does not relax these gates.

## Files and traceability

- [GitHub evidence](github_evidence.jsonl), [HN evidence](hn_evidence.jsonl)
- [Historical trend baseline](trend_baseline.jsonl)
- [Merged evidence](merged_evidence.jsonl), [ledger and 8 claims](evidence_ledger.json)
- [Hypothesis evaluations](opportunity_evaluations.json), [empty opportunities CSV](opportunities.csv)
- [Run manifest](run_manifest.json), [verification](verification.json)
- [Offline test report](offline-tests/offline_tests.json) and [log](offline-tests/offline_tests.txt)
- ws1/ and ws2/: frozen protocols, checkpoints, raw bytes, metadata and logs,
  including the HN initial sandbox failure. ws3/: historical provenance review,
  superseded proposal and effective user-directed baseline protocol.

The live client uses domain-scoped anonymous HTTPS GET, redirect refusal,
bounded attempts/request budgets, per-source minimum intervals, socket timeouts,
body size bounds and request/ingress/checkpoint logs. Time budgets are checked
between operations, not a proven hard wall-clock cancellation for slow reads.
Error-body capture is bounded to 16 KB and may be partial. No paid API, local
secret file, posting, email or payment was used by the acquisition code.
Runtime model consumption/dollar cost is not independently metered here; an
account usage limit was observed, so no token/dollar-budget compliance is invented.

## Next decision

Review GH07/GH08/GH09 and HN10/HN11 as **leads**, not opportunities. If approved
later, narrow the next query protocol and seek public, verifiable buyer/product/time
proof within the allowed domains; if unavailable, keep the GAP. Define how to
reobserve only existing measured baseline IDs before any T+7/T+14 run. Do not
invent missing GitHub historical metrics or treat current issue discovery as a
follow-up to the older repo cohort. No further live run, new domain, cron, model
worker or purchase is authorized by this report. Stop after commit/push for review.
