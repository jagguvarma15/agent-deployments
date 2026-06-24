# Skills — Cost and Latency

> Token math + p50/p95 expectations for the registry, the matcher, the body load, and the script run.

## The economics in one paragraph

Skills exist to bend the cost curve. A monolithic system prompt costs `tokens_per_skill × num_skills × tokens_per_call`. A skill registry costs `tokens_per_registry_entry × num_skills + tokens_per_picked_skill × num_active × tokens_per_call`. Because `tokens_per_registry_entry` is ~30-50 and only the picked skills' bodies are loaded, the registry version is 10-100× cheaper for the same agent shape once `num_skills > 5`. That asymmetry is the whole pattern's reason to exist.

## Token costs per turn

Tracking the costs by layer:

| Layer | Token cost per turn | Notes |
|---|---|---|
| Recipe system prompt | ~500-2000 | Fixed per recipe; doesn't grow with skill count. |
| Skill **registry surface** (lookup metadata for all N skills) | `N × ~40` | The minimum cost of having skills registered. |
| Stage 1 matcher | 0 LLM tokens | Pure pattern matching, no LLM call. |
| Stage 2 judge LLM call | ~800-1500 prompt + ~30-80 response | One small-LLM call per turn that needs it. |
| Picked skill **body** | `~500-2000 per active skill` | Loaded only when picked; typically 0-2 active per turn. |
| Helper script output | `0-500` | Subprocess output, fed back into agent. |

### Example: a recipe with 50 skills, 1 typically active

- Registry surface: 50 × 40 = **2,000 tokens** (constant across all turns).
- Stage 2 judge: ~1,200 tokens prompt + 50 response × $0.001/1K (Haiku) = **~$0.001 per turn**.
- Picked skill body: 1 × ~1,500 = **1,500 tokens** added to the main agent call.
- Helper script output: ~300 tokens.

Compare to inline-prompt approach:
- 50 procedures × 800 tokens each = **40,000 tokens** every turn.

The skill-pattern saves ~36K tokens per turn at recipe steady state. At Sonnet-4.6 pricing (~$3/M input, $15/M output) and 100K turns/day, that's ~$108/day in saved input cost — about **$40K/year** for one production agent.

## Latency budget

| Step | Typical p50 | Typical p95 | Notes |
|---|---|---|---|
| Boot-time `SkillRegistry.load()` | 5-50 ms | 100 ms | Once per process start; not per-turn. |
| Stage 1 keyword match | <1 ms | <5 ms | In-memory dict scan over triggers. |
| Stage 2 judge LLM call | 200 ms | 500 ms | Haiku-class single-shot judgment. |
| Body file read + injection | <5 ms | <20 ms | Filesystem read; fast on SSD. |
| Helper script subprocess (in-process) | 200 ms | 2 s | Dominated by what the script does. |
| Helper script subprocess (sandboxed) | 300 ms - 1 s cold | 2-5 s cold | First sandbox spin-up; warm sandbox is comparable to in-process. |

The hot-path overhead skills add per turn is ~250 ms (Stage 2 + body inject), assuming the skill itself doesn't run heavy scripts. That's small compared to typical agent reasoning calls (1-5 s for Sonnet on a non-trivial query).

## When the costs stop being negligible

The pattern's economics break in three places:

### 1. Very large registries (> 1,000 skills)

The registry surface starts to matter. At 1,000 skills × 40 tokens = 40K tokens just for lookup metadata, you're back into the territory of expensive inline prompts. Mitigations:

- **Per-role registries** — load only skills the active role can use.
- **Domain routing** — a [`Routing`](../../patterns/routing/overview.md) layer in front of the matcher picks the skill domain first; only that domain's skills land in the lookup table.
- **Tiered loading** — Tier 1 always-loaded skills; Tier 2 loaded after a domain decision.

### 2. Skills with very long bodies

A SKILL.md body of 10,000 tokens crowds out the conversation history and other context. Mitigations:

- Hard cap on per-skill body size (e.g., 3,000 tokens) at lint time.
- Move detail into helper scripts and have the skill body explain *when to run them*, not duplicate their content.
- Split long skills into a short selector skill that decides which detailed skill to delegate to next.

### 3. Hostile / heavy helper scripts

A script that runs for 30 seconds blocks the agent's turn. Mitigations:

- Sandbox with per-script timeout (typical: 30 s hard limit).
- Async invocation patterns — the skill kicks off the script, returns a job id, and the agent polls.
- Move heavy work to a background job queue and have the skill report status.

## Cost vs. quality tradeoffs

| Optimization | Saves | Loses |
|---|---|---|
| Skip Stage 2 LLM when Stage 1 returns 0-1 candidates | ~$0.001 + 250 ms per turn (when applicable) | Some judgment on edge cases. |
| Cap body tokens at injection | 30-50% body cost reduction | Detail in long skills. |
| Use Haiku-class for Stage 2 (vs. Sonnet) | 10× cost reduction | Slightly noisier judgment. |
| Cache helper script outputs by (skill_id, input_hash) | Helps when same input recurs | Stale results if the underlying data changes. |
| Pre-filter via routing layer | Big at large N | Adds one more LLM call per turn. |

The default-good choice: Haiku Stage 2, no body caching, no routing layer until N > 500. Add complexity when metrics demand it.

## Budget envelope by deployment

| Deployment | Reasonable per-turn skill overhead |
|---|---|
| Single-user CLI / IDE agent | 1-2 ms + ~0 LLM cost (small registries, often skip Stage 2). |
| Customer-facing SaaS chatbot | 50-300 ms + ~$0.001 (Haiku Stage 2, ~50-skill registry). |
| Multi-tenant enterprise agent | 200-500 ms + ~$0.005 (per-tenant grants + routing layer). |
| Multi-agent orchestrated system | Per-role; supervisor often has 0 cost (no skills). |

If your skill overhead is more than 10% of total turn cost or latency, the pattern is being misused — usually too many skills, too-large bodies, or running heavy scripts in-line.

## Watching for cost drift

The three signals that suggest costs are creeping up:

1. **Body token p95 trending up** — skills growing too verbose. Lint at commit time.
2. **Stage 2 judge cost trending up** — registry growing without per-role slimming.
3. **Script duration p95 trending up** — helper scripts taking on too much work.

Address each in <1 sprint when noticed. Skills' economics are forgiving until they're not; small drifts compound across thousands of turns/day.

## See also

- [`overview.md`](./overview.md) — when to use skills at all.
- [`design.md`](./design.md) — the components these costs map to.
- [`implementation.md`](./implementation.md) — body caps and per-skill limits.
- [`primitives/tool_use/cost-and-latency.md`](../tool_use/cost-and-latency.md) — comparable pattern costs.
- [`foundations/cost-and-model-selection.md`](../../foundations/cost-and-model-selection.md) — model choice for Stage 2.
