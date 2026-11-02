# Agent schema verification — STOP at Step 1

Historical Step 1 report. The user subsequently approved proceeding with only
name/description/developer_instructions/model/model_reasoning_effort and
parent-enforced evaluator sandbox permissions. See deployment_report.md for the
later implementation; the stop/result below records what was known at Step 1.

Date: 2026-11-02 (Asia/Saigon).
Workspace: `D:\Projects\radar-money-online`.
Baseline commit: `77f64446ef85778ee6cf1cc3d3979f868f6461ce`.

Result: **MISMATCH — do not proceed to Steps 2–6.**
No agents, hooks, smoke sessions or production runs were created or started.
No commit/push was performed in this verification step. No secret files were read.

## Local command verification

Executed `codex --version`: `codex-cli 0.166.0`, exit code 0.

Executed `codex agents --help`, exit code 0. Relevant verbatim output:

```text
Browse all agent sessions on the shared local app-server daemon

Usage: codex agents [OPTIONS]

Options:
  -c, --config <key=value>
      --enable <FEATURE>
      --remote <ADDR>
      --disable <FEATURE>
      --remote-auth-token-env <ENV_VAR>
  -C, --cd <DIR>
      --no-alt-screen
  -h, --help
```

The options listing above omits help paragraphs and examples; it does not add
any options or subcommands. There is no `list` subcommand advertised by this
installed CLI's help. This command is a session browsing TUI, not a verified
custom-agent TOML schema or installed-role listing interface. Consequently,
`codex agents list = 13` is not a validated acceptance test for this CLI.
`codex agents list` itself was not run; no interactive TUI was opened.

Both help/version commands also emitted warnings about access denied when
cleaning stale arg0 temp directories and creating PATH aliases under the user's
Codex temp directory. Their exit code remained 0. These warnings are recorded
but are not the reason for the schema stop; no permissions were changed.

## Official documentation checked

Searched official OpenAI documentation and fetched the custom-agents section:

- [Subagents — Custom agents](https://learn.chatgpt.com/docs/agent-configuration/subagents#custom-agents)
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands#command-overview)

The custom-agent documentation supports standalone project TOML files under
`.codex/agents/`. It requires `name`, `description`, `developer_instructions`.
It documents `model` and `model_reasoning_effort` as custom model settings,
along with other optional controls such as model verbosity and supported
capability reductions. Additional documented optional fields need not be used.

Crucially, it states that custom agents inherit parent permissions and other
session settings; putting `sandbox_mode` in a custom agent file does not
override the parent configuration. This is a runtime permission mismatch,
not a claim that the text is invalid TOML or that every parser rejects it.

## Comparison against the requested allowlist

| Field | Requested behavior | Verified result |
|---|---|---|
| `name` | Required | Confirmed required |
| `description` | Required | Confirmed required |
| `developer_instructions` | Required | Confirmed required |
| `model` | Optional override, requested gpt-6.1-sol | Documented; official examples use gpt-6.1-sol subject to account access. No model call/access test performed |
| `model_reasoning_effort` | Optional override | Documented; no agent spawn performed |
| `sandbox_mode` | workspace-write for scouts/analysts, read-only for evaluators | **Mismatch: custom file does not override parent sandbox permissions** |
| `nickname_candidates` | Optional | Not established by the fetched custom-agent schema documentation; do not assert verified support or rejection |
| `max_turns` | Excluded | Not used; no claim of verified support |
| `token_budget` | Excluded | Not used; no claim of verified support |

An instruction saying “do not edit files” is not an enforced read-only sandbox.
Writing `sandbox_mode = "read-only"` into evaluator TOMLs would not establish
the requested boundary on the evidence checked here. Do not silently substitute
instructions for permission enforcement, remove the field and claim equivalence,
or report the requested schema as fully verified.

## Stop condition and next decision

The user's instruction explicitly requires stopping after Step 1 when schema
differs from expectations. That condition is met by the sandbox override behavior.
The CLI listing assumption is an additional validation blocker.

Before resuming, revise/approve how evaluator permissions will be enforced in
the parent execution context and how custom-role discovery will be verified
with this installed version. Omit nickname_candidates unless support is separately
verified. Preserve the requested model; do not silently substitute another model.

Hooks, PreCompact/PostCompact availability, token-usage events, rollback behavior,
13-role discovery and the three smoke tests remain **NOT IMPLEMENTED / NOT RUN**.
No test results, token usage or deployment success are inferred from this check.
