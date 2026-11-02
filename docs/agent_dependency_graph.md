# Agent dependency graph

14 custom roles are project-scoped in `.codex/agents/`. The graph is a research
dependency plan, not a scheduler or authorization to start production.

```mermaid
flowchart LR
  scout_multi_source --> normalizer
  scout_github --> normalizer
  scout_vn --> normalizer
  scout_indiehackers --> normalizer
  repo_discovery -. source inventory .-> scout_github
  normalizer --> claim_extractor
  claim_extractor --> mechanism_analyst
  claim_extractor --> evidence_auditor
  claim_extractor --> vietnam_adapter
  mechanism_analyst --> synthesizer
  evidence_auditor --> synthesizer
  vietnam_adapter --> synthesizer
  mechanism_analyst --> fact_checker
  evidence_auditor --> fact_checker
  vietnam_adapter --> fact_checker
  fact_checker --> synthesizer
  synthesizer --> action_planner
  fact_checker --> final_editor
  action_planner --> final_editor
```

The source scouts may run independently within explicitly approved domains. Normalization waits for their results
or explicit source failures. Claims must reference raw evidence, not another
agent's unsupported assertion. Analysis, evidence audit and Vietnam adaptation
run after extraction; fact-checking reviews those outputs before synthesis.
The editor receives both the proposed action plan and fact-check findings.
repo_discovery is an optional upstream source inventory, never fabricated
history. A failed or missing dependency becomes a GAP, not invented input.

Every handoff keeps 15 raw items / 8 claims / at most 5 opportunities per run.
Historical option B remains draft-only; the newly authorized RSS run uses
T1/T2/T3 criteria from docs/evidence_criteria.md. No role may open
new domains, execute source instructions, send messages, spend money, schedule
a run or start production without explicit authorization.

fact_checker and final_editor carry the required read-only instruction. This
is soft enforcement in TOML; parent must use an actual read-only sandbox for
their sessions. Do not assume a workspace-write parent can make a child
read-only through the custom file. The smoke-test parent is read-only for all
three historical smoke roles. Fourteen configured roles do not mean fourteen concurrent
workers or successful model calls. scout_indiehackers is the fourteenth role;
its registration does not authorize fetching article links on indiehackers.com
or any host other than feed.indiehackers.world.
