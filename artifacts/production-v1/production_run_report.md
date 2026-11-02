# Production Run v1 — draft-only baseline

Run ID: **baseline-20261102**.
Verdict: **RESEARCH_DRAFT_ONLY**.
Technical end-to-end outcome: **PASS**, business qualification: **STOP**.

This is **offline_archive_replay**, using the implemented and reviewed option B.
It is not a new live collection, third-source integration, longitudinal sample,
or claim that the system is production-ready. Exactly one baseline execution
completed; no second/live run was started.

## Actual results

| Metric | Observed result |
|---|---:|
| Retained raw records replayed | 15 |
| GitHub repository records | 10 |
| HN Algolia story records | 5 |
| Claims | 8 |
| Opportunities | 0 |
| New source HTTP requests | 0 |
| Enabled web-search adapters | 0 |

Execution ran on 02/11/2026 at approximately **11:51:26 Asia/Saigon**
(04:51:26 UTC). Exact event timestamps are in the ingress log. Source retrieval
timestamps remain 03:01:40 UTC for GitHub and 03:01:44 UTC for HN; they were not
rewritten to the baseline time. Both archives fall within the seven-day
retrieval window. Their historical HTTP 200 responses are not new HTTP results.

The request mentioned GitHub + HN + optional web search. The actual script has
only two archive adapters and network_enabled=false. No web-search adapter or
live fallback was added. After explaining this distinction in chat, execution
stayed within reviewed B. No unanswered choice was treated as approval to add live.

Verdict distribution for the eight claims: OBSERVED_METADATA=8, HYPED=0,
EMERGING=0. HYPED is only an upper bound for metadata, not an automatic label.
The CSV has one header row and no opportunity data rows.

## Execution and approval

The literal command `python scripts/run_production.py` was first rejected by
argparse because --approval-file and --run-id are required. No pipeline run
started from that command. The correction supplied explicit required arguments,
without removing or weakening the approval gate:

```powershell
python scripts/run_production.py --config config/production_v1.json --approval-file config/approvals/baseline-20261102.json --run-id baseline-20261102
```

This execution exited 0 and emitted the draft artifact directory. The approval
record derives from the user's explicit acceptance of deployment_report.md and
request to run v1 in this chat. The stored approved_at is the time that existing
authorization was recorded locally, not an independently signed identity claim.

The old 54-test report was stale relative to source after the agent sprint.
Config was rebound to a new preflight report; **69 offline tests PASS**, 0 errors,
0 failures. The runner blocked socket creation. Existing historical reports
were preserved. One new regression checks that publishing root dashboard.md
cannot change the separately approved dashboard template.

Template moved to templates/dashboard.md; dashboard.md now displays the actual
baseline results. The production bundle hash follows the configured template,
so this post-run display update does not invalidate the run's input approval.

## Triggered kill criteria / GAP summary

| Recorded criterion | Meaning for this baseline |
|---|---|
| NO_VERIFIED_BUYER_OR_PAYMENT_EVIDENCE | Search metadata does not establish a verified buyer or transaction |
| NO_LONGITUDINAL_TREND_EVIDENCE | Replaying one snapshot does not create a second measurement or establish growth |
| MISSING_BUYER_EVIDENCE | No buyer identity linked to a specific product/time and verified proof |
| MISSING_PAYMENT_EVIDENCE | No receipt/invoice/contract/public filing satisfying the defined linkage and verification requirements |
| MISSING_TREND_EVIDENCE | No predeclared same-cohort/same-metric T0 plus T+7/T+14 measurements |
| OPTION_B_KEEP_DRAFT | Proof verification and positive qualification are intentionally unavailable in B |

The first two reasons remain unconditional capability blockers in the current
gate implementation, not candidate-specific measurements. No source-minimum
kill was triggered: 10 GitHub repos and 5 HN stories satisfy the count minimums.
No archive validation error was recorded. The stop was expected evidence policy,
not a parser/network failure. No source acquisition continued after the gate.

## Traceability and artifacts

- [Run manifest](baseline-20261102/run_manifest.json): status, counts, approval,
  input/source hashes and output artifact hashes.
- [Evidence ledger](baseline-20261102/evidence_ledger.json): eight claims and raw
  evidence references. Raw files still point to immutable artifacts/mvp-v1 responses.
- [Ingress log](baseline-20261102/ingress.jsonl): config binding, two archive
  ingresses/validation passes and terminal run_stopped event.
- [Opportunities CSV](baseline-20261102/opportunities.csv): empty data set.
- [Per-run dashboard](baseline-20261102/dashboard.md): immutable rendered results.
- [Preflight report](preflight/offline_tests.json) and [log](preflight/offline_tests.txt).
- [Initial CLI check](cli_initial_check.json): failed argument validation, no run.
- [Post-run verification](post_run_verification.json): independently checked
  hashes, evidence references, counts, historical byte preservation and report hashes.

No receipt, revenue estimate, verified incident, growth figure or new business
case was inferred. No agents/model calls, API purchase, post, email, payment,
cron or domain expansion was executed by this baseline. It verifies the
deterministic approval/config/archive/claim/gate/report path, not the 13-agent
dependency graph or live network reliability.

## Recommendation and stop

Recommend **C: keep draft and review this baseline**, then separately approve a
small reliability/claim-to-raw verification improvement or targeted live protocol.
Options A/B/C with estimated cost, time, success limits and risks are in
docs/next_after_production_v1.md. No additional live run or next option is selected
for execution by this report.

Preserve LICENSE and all prior evidence/test reports. Commit/push this baseline
with the requested message, report the resulting SHA in chat, then stop for review.
