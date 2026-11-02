# WS-3 completion after user clarification

The user confirmed the 12 old “Cổng 2” cases do not exist in this workspace;
the dead cloud session was not carried over. No further search for them is needed.

The final trend_baseline.jsonl uses exactly the 15 original MVP records and
references all eight historical claims. It preserves their original T0 retrieval
times. Only five HN records have actual numeric metrics in the normalized MVP
ledger (points/comments); ten GitHub repository records have no retained metric.
No metric is invented for those ten records. T+7 and T+14 are null for every row.

**Thiếu longitudinal trend evidence — chỉ có 1 snapshot.** The baseline v1
replay is not an independent observation. Current issue/comment discovery uses
different entities and queries; it is not joined as a longitudinal follow-up.

protocol.json is the initial discovery-cohort proposal, superseded by the user's
clarification. effective_protocol.json governs the final output. The initial
two-line trend output is preserved in trend_initial_proposal.jsonl. No proposed
new cohort/metric is represented as observed history or applied in the final file.

All three runtime subagents hit the account usage limit after WS1/WS2 outputs
were saved. The orchestrator finalized this historical-only WS3 output locally,
checked hashes and retained the GAP. No new model worker, source request, future
measurement or schedule was created to work around the limit.
