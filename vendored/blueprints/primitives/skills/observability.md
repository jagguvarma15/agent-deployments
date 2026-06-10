# Skills — Observability

> What to trace per skill invocation, what to log, and what alarms matter.

## Per-turn skill trace

Every turn that involves skill selection should emit a structured trace span. Recommended shape:

```yaml
span: skill_selection
attributes:
  agent.role: "researcher"
  user_message_summary: "<first 200 chars>"
  registry.size: 47
  registry.size_after_grants: 12          # after grant-policy filter
  stage1.matched_count: 3
  stage1.matched_ids: [web-search-loop, citation-formatting, summarize]
  stage2.judge_model: "claude-haiku-4-5"
  stage2.picked_ids: [web-search-loop]
  stage2.picked_reasoning_summary: "<first 200 chars>"
  decision.fired: true                    # at least one skill activated
  decision.empty: false                   # no skill activated
duration_ms: 47
```

For each skill that actually activated:

```yaml
span: skill_invocation
attributes:
  skill.id: web-search-loop
  skill.version: 0.3.0
  body.tokens: 1247                       # measured at injection time
  scripts.invoked: [scripts/search.py, scripts/extract.py]
  scripts.duration_ms: 1842
  outcome: completed                      # completed | errored | aborted
  outcome.error_class: null
duration_ms: 1923
```

Cap the trace at sensible levels — don't ship the full body verbatim every turn (that's what `body.tokens` is for). Sample the body content into traces at low rates (1-5%) for retrospective debugging.

## OpenTelemetry mapping

Per [`agent-deployments/docs/stack/opentelemetry.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/stack/opentelemetry.md), skill spans should attach the GenAI semantic conventions where applicable:

- `gen_ai.system` — set to the judge model's vendor (e.g., `anthropic`) on `skill_selection` when Stage 2 fires.
- `gen_ai.request.model` — the judge model id (`claude-haiku-4-5-20251001`).
- `gen_ai.token.usage.input` / `gen_ai.token.usage.output` — judge call's token counts.
- Skill body token measurement uses a non-genai attribute (`agent.skill.body.tokens`) since it's not a model call.

## Logging vs. tracing

| Signal | Channel |
|---|---|
| Per-turn selection (which skills activated) | Trace span. |
| Per-skill invocation outcome | Trace span. |
| Authoring errors (SKILL.md fails to parse at boot) | Structured log + startup failure. |
| Grant denials | Trace span attribute + structured log. |
| Trigger collisions (Stage 1 returned > N candidates) | Trace span attribute + structured log warning. |
| Skill script subprocess output | Captured into the invocation span. |
| Skill body injection costs aggregated by skill | Metric (histogram). |

## Key metrics

The handful of metrics worth tracking continuously:

| Metric | Why it matters |
|---|---|
| `skill_activation_rate` (% of turns that fire at least one skill) | Sudden drops mean Matcher is failing — usually a trigger drift after a model upgrade. |
| `skill_activation_count` per skill id | Identifies dead skills (never activate) and overfiring skills (activate too often). |
| `skill_body_tokens` histogram per skill | Catches skills that have grown bloated. |
| `skill_script_duration_p95` | Catches scripts that have become slow. |
| `skill_judge_latency` (Stage 2 LLM call) | Stage 2 is on the hot path; aim for <200 ms p95. |
| `grant_denial_count` | A spike usually means a misconfigured role. |

## Alarms

Three alarms catch most production-relevant skill failures:

1. **`skill_activation_rate` drops > 30% week-over-week.** Strong indicator that trigger matching is broken (model change, trigger drift). Trace the recent changes to skill files and model versions.

2. **A single skill's `skill_activation_count` falls to 0 for > 24h.** Either the skill is no longer needed (delete it) or its triggers have stopped firing (fix or remove).

3. **`skill_script_duration_p95` > N seconds (recipe-specific budget).** A skill that used to be fast and isn't anymore is a regression — usually a transitive dependency change.

## Trace inspection workflow

When a user reports "the agent didn't do X right":

1. Pull the trace for that turn.
2. Check `skill_selection.decision.fired` — did any skill activate?
3. If not, check `stage1.matched_count` — did keyword matching find anything?
4. If yes but `stage2.picked_ids` is empty — read `stage2.picked_reasoning_summary` to see why the judge rejected the candidates.
5. If a skill did activate, walk the `skill_invocation` spans for unexpected scripts or errors.

This workflow takes <60 seconds with good traces and turns "the agent did something weird" into either a skill bug, a trigger bug, or a grant bug — actionable categories.

## What NOT to log

- **Full SKILL.md bodies on every turn.** Sample, don't dump.
- **User message verbatim in traces.** Summarize (first N chars) or hash; respect PII policies.
- **Per-token judge model output.** Aggregate into a single span attribute.
- **Skill script stdout when it's hundreds of KB.** Truncate; link to the artifact in your storage.

## See also

- [`design.md`](./design.md) — the components these traces describe.
- [`implementation.md`](./implementation.md) — where in the code to emit the spans.
- [`agent-deployments/docs/cross-cutting/observability.md`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/cross-cutting/observability.md) — the production-side observability story.
- [`composition/agentic-eval-pipeline.md`](../../composition/agentic-eval-pipeline.md) — how skill traces feed trajectory eval.
