# WS-3 — baseline integrity audit

**BASELINE_INTACT_WITH_GAPS / integrity PASS**. Offline read-only audit, no source requests or follow-up measurements.

The original frozen cohort remains exactly 15 records: 10 GitHub repositories and 5 HN stories, with E01–E15 identities unchanged. Every baseline/raw hash matches its manifest and committed HEAD bytes. Reconstruction from original raw responses matches snapshot_t0.jsonl exactly.

T0 remains 02/11/2026; scheduled T+7 is 09/11/2026 and T+14 is 16/11/2026, preserving each source's original UTC anchor. Follow-up timestamps, counters and deltas remain null; comparable and trend_evidence_present remain false. No cron, scheduler or follow-up authorization was created.

HN points/num_comments exist. Verified GitHub stars, total issues and specific issue comment counters are absent/null. Literal followers and labeled issue counters must not substitute for those missing metrics. The trend protocol was registered after original T0; this audit does not fix that limitation.

WS-3 contributes **zero discovery raw items and zero new claims**. Its 15 historical members must stay separate from the WS-1/WS-2 evidence merge. The baseline files and MVP artifacts were not modified.

See audit.json for exact input hashes, source anchors and GAP codes. This is not a T+7/T+14 run or payment evidence.
