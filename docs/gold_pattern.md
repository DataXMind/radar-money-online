# Gold Pattern integration

Scope: project custom agents and lifecycle hooks only. No research pipeline,
production run, source fetch, cron or new domain is enabled by installation.
Official references: [hooks](https://learn.chatgpt.com/docs/hooks),
[custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents).

## Registration and trust

`.codex/hooks.json` registers six handlers: PreToolUse/token guard,
PreCompact/save, PostCompact/restore, SessionStart(compact)/restore,
Stop/output validator and SubagentStop/output validator. Windows commands use
PowerShell + Python, resolve scripts from the Git root, and have a 5-second
timeout. POSIX commands use python3. Inputs are stdin JSON, outputs stdout JSON;
event input is never interpolated into a shell command. No transcript is opened.

Run `python scripts/install_gold_pattern.py` after reviewing changes. It merges
hooks while preserving unrelated groups, backs changed files up as
`.bak.<UTC timestamp>.<unique suffix>`, and does not rewrite identical content.
Registry `.codex/gold-registration.json` records owned groups and agent hashes.
Do not hand-edit the ownership registry. Files/state/backups are local; state
and backups are ignored by Git.

Codex requires trust for the exact hook definitions. Installation does not
bypass this. Use `/hooks` to review/trust. The user explicitly approved the six
project hooks in this chat after automatic approval review initially rejected
the trust action. The native CLI subsequently showed all six active.
Trust is local to this host/user; a clone is not automatically trusted.
Hooks can execute outside the session sandbox; only these reviewed scripts
should be trusted. Script edits must be reviewed too, even when a command's
definition hash does not change. Agent tools remain subject to parent permissions.

## Token warnings, not a hard budget

`.codex/hooks/token_guard.py` warns at >=80,000 and >=95,000 measured input plus
output tokens. Cached-input tokens are already part of input_tokens and are not
added again. Data is keyed by hashed session ID and measured turn ID; replaying
the same measured turn does not increase the total. Updates use an exclusive
lock and atomic state writes; a stale lock is reported, not deleted blindly.

Native lifecycle payloads do not guarantee usage counters. Such events log
usage_unavailable and do not fabricate a zero or estimate. A warning cannot
enforce an account billing ceiling or stop tokens spent between events.
`scripts/verify_agent_smoke.py --relay-usage` reads the bounded, archived CLI
JSONL, verifies role signatures and relays real turn.completed usage to
`.codex/state/token-usage.jsonl`. This is an explicit adapter invocation, not
an automatically wired provider callback. Other entry points must supply their
own vetted measured-usage adapter; without it there is no measured budget coverage.
Parent CLI usage is not separately verified child usage or a dollar-cost estimate.

## Compact context safely

PreCompact saves only `.codex/context.md`, a reviewed, size-bounded project note,
with SHA-256 under `.codex/state/context-<session-key>.json`. This is not a full
conversation backup and will not capture unsaved work or pending decisions
automatically. Update reviewed notes before compacting if project state changes.
No prompts, transcripts, credentials or environment variables are harvested.

PostCompact emits bounded notes using supported systemMessage output.
SessionStart(compact), when emitted by the runtime, additionally restores notes
as additionalContext with a 1,500-token spill threshold. Checksum/source changes
or unsafe state paths are rejected. The context round-trip was tested offline;
an actual model compaction was not requested in this sprint.

## Structured output contract

For a research handoff, return JSON (or a json fenced block):

```json
{
  "status": "RESEARCH_DRAFT_ONLY",
  "raw_items": [],
  "claims": [],
  "opportunities": [],
  "gaps": ["No source records supplied; buyer/payment/trend proof missing"]
}
```

This is a synthetic empty example, not new evidence. Nonempty raw records need
unique evidence_id, approved source URL, response_body beneath artifacts/ and
response_sha256 matching the actual file. Claims need unique claim_id,
statement and nonempty evidence_ids referencing those records. Limits remain
15/8/5, and option B requires opportunities=[]; EMERGING claims are rejected.
This does not independently prove that a claim's words follow from the raw
body or that remote content is true. Evidence audit/fact-checking are still required.

Stop/SubagentStop validate only structured research outputs. Ordinary coding
messages and unrelated JSON are explicitly marked unvalidated, never PASS.
Invalid research output requests one correction; a repeated stop_hook_active
failure stops for human review instead of an infinite loop. Hook failure or
timeout is reported but is not a complete security boundary. Agents must not
use unstructured output to evade research review.

## Rollback and idempotence

`python .codex/hooks/uninstall.py` unregisters exact owned groups, preserves
unrelated/modified groups, and backs up the changed hooks file. It leaves agent
definitions, scripts and source evidence in place. It does not change global
hooks, global trust records or account settings. Modified owned groups require
manual review; do not assume they were removed by exact-match rollback.

Optional `--remove-agents` archives and removes only hash-matching registered
agent definitions. It refuses modified definitions; inspect the backups before
restoring anything. Both modes are tested with temporary files, not invoked on
the deployed project. Reinstalling identical registration causes no file changes
and no extra backup. Do not install/uninstall concurrently.

## Verification boundaries

Offline tests cover TOML allowlist, token warning thresholds/dedup/unknown usage,
context round-trip/tampering, stdin/stdout validator protocol, unsafe paths,
output caps/evidence hashes and installer/rollback behavior. Live model smoke
only used synthetic empty research input for three roles, under a read-only
parent. It did not fetch sources or execute production.
