# Deployment report — 13 agents + Gold Pattern

Date: 2026-11-02 (Asia/Saigon). Repo: `D:\Projects\radar-money-online`.
Baseline: `77f64446ef85778ee6cf1cc3d3979f868f6461ce`.
Scope: agent configuration and hook integration; **not production pipeline deployment**.

## Result

| Check | Result | Evidence / limitation |
|---|---|---|
| 13 TOMLs parse | PASS | Exact five-field allowlist, name/filename match, gpt-6.1-sol, medium/high effort |
| Evaluator instructions | PASS | fact_checker/final_editor contain required no-file-edits line; parent must enforce read-only sandbox |
| Dependency graph | Created | docs/agent_dependency_graph.md; repo_discovery is optional upstream inventory |
| Runtime custom role visibility | PASS | Runtime parent reported all 13 available role names; smoke_verified.json |
| CLI agent browser | Opened | codex agents command center inspected; this is a session browser, not a 13-TOML registry |
| Three role smoke tests | PASS | scout_multi_source, evidence_auditor, vietnam_adapter returned their distinct role signatures, canonical task names and draft/missing-proof results |
| Offline regression suite | PASS | 68 tests, 0 failures, 0 errors; socket creation blocked in runner |
| Gold-specific offline checks | PASS | 14 of the 68 tests cover TOMLs, token/context/validator/install/rollback contracts |
| Hook registration | PASS | Six command handlers in .codex/hooks.json; native CLI recognized them |
| Hook activation | PASS on this host | User explicitly approved trust after an automatic-review rejection; native /hooks browser then showed all six active |
| Idempotence/backups | PASS | First install changed registration, second did not; changed registration backed up as .bak.timestamp.suffix |
| Production execution | NOT RUN | No artifacts/production-v1 run directory, no cron, no source refresh |
| Git commit/push | Separate final verification | Exact delivery SHA and push outcome are reported in the chat; not embedded into its own commit |

Runtime smoke used `codex exec --json --ephemeral --sandbox read-only --model
gpt-6.1-sol`. Three role markers came from their developer_instructions, not
the smoke prompt. The parent was instructed not to read files or source data.
The second smoke disabled apps/plugins and untrusted hooks to reduce unrelated
surface. It returned canonical task names rather than separate UUIDs.
The CLI JSON stream is not a complete child tool-call audit: marker checks and
the parent's runtime responses are the preserved evidence, not an invented
full trace of every child invocation.

The first smoke lacked independent role markers; it is retained as a preliminary
run, not the acceptance proof. The marker-based smoke reported one wait call
aborted before dispatch followed by successful waits. Startup logs also warned
about an ignored user-level disable_response_storage setting, credential-store
fallback metadata (no credential values), and ephemeral parent transcript lookup.
No user configuration or credentials were inspected or edited to suppress these.

## Files and reproducible checks

- `.codex/agents/*.toml`: the 13 custom role definitions.
- `.codex/hooks/*.py`: token guard, save/restore, output validator, rollback and common I/O.
- `.codex/hooks.json`, `.codex/gold-registration.json`: registration and ownership.
- `.codex/context.md`: reviewed context note; no transcript scraping.
- `scripts/install_gold_pattern.py`: idempotent registration.
- `scripts/verify_agent_smoke.py`: offline verification and measured usage relay.
- `artifacts/agent-sprint/offline_tests.json` / `.txt`: actual 68-test report/log,
  including source and agent-bundle SHA-256, log hash and production bundle hash.
- `artifacts/agent-sprint/runtime-smoke-v2.jsonl`, `smoke_prompt_v2.txt`,
  `smoke_verified.json`: real runtime smoke evidence, distinct from synthetic tests.
- `artifacts/agent-sprint/hook_activation.json`: operator-observed native CLI
  activation record and config hash; not a screenshot or cryptographic trust attestation.

Offline reproduction (no model/source network calls):

```powershell
python -m money_trend.offline_tests --output artifacts/agent-sprint
python scripts/verify_agent_smoke.py
```

Re-running tests changes the report timestamp/log duration; review the committed
version for the original evidence. Re-running smoke verification without
--relay-usage does not write token state or make another model call.

## Five Gold Pattern points and limits

1. **Token guard:** warnings at 80K/95K, local metadata-only log at
   `.codex/state/token-usage.jsonl`, no hard cap or billing guarantee. Native
   events without usage are marked unavailable. Measured usage is relayed from
   CLI turn.completed, deduplicated per session/turn. Acceptance smoke parent
   input=109727, output=846, total=110573 including cached input already within
   input_tokens. The relay emitted a real 95K warning. The 80K boundary is tested
   with synthetic offline events. Child usage and dollar costs were not verified.
2. **Compact context:** PreCompact saves reviewed notes only; PostCompact emits
   the notes, SessionStart(compact) can inject bounded additionalContext. The
   round-trip/checksums were tested offline; no actual model compaction was run.
3. **Output validator:** checks structured draft shape, limits, evidence IDs,
   local raw file hashes and empty opportunities. Unstructured coding replies
   are explicitly not validated. It cannot independently prove source truth.
4. **Rollback:** default uninstall unregisters only exact owned hooks, backs up
   the changed file and preserves unrelated/modified groups. Optional agent
   removal refuses modified definitions and archives before removing. Tests
   use temporary directories; deployed rollback was not invoked.
5. **Idempotence:** identical installs do not rewrite config or produce extra
   backups. Changed owned configuration gets timestamped backup. No recursive
   deletion, global hook changes or secret collection is implemented.

Hook trust can allow scripts to run outside the session sandbox. An initial
trust attempt was denied by automatic approval review because creation/review
authorization did not explicitly cover activation. Work continued without
bypassing the rejection; the user then approved exactly six project hooks, and
native trust succeeded. This host-local trust is not transferred by Git.
Other hosts must review/trust the definitions themselves. Script edits require
review even if the hook command string remains unchanged.

## Safety and handoff

No new public-source evidence, buyer/payment proof or trend series was produced.
Original LICENSE, artifacts/mvp-v1 and historical reports remain unchanged.
No production run, paid API integration, email, posting or payment was executed.
Codex runtime/model smoke calls used the existing account; no API credential
files were opened by the implementation or smoke task. CLI account usage is
recorded above; this report makes no claim of zero account cost.

RESEARCH_DRAFT_ONLY remains the only supported qualification outcome under B.
Installing 13 roles does not execute the dependency graph or authorize live
research. Parent read-only enforcement is required for evaluator sessions;
soft instructions alone are insufficient. Existing production config's old
54-test report no longer matches the current source/tests and will fail closed;
any future production approval needs a current reviewed report/config bundle.

Stop after committing/pushing this sprint and wait for the user's next decision.
See docs/gold_pattern.md for operation, warnings, trust and rollback boundaries.
