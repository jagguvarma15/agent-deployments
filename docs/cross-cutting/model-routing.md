# Cross-cutting: Model routing

**Concern:** Pick the right model per role, with documented fallbacks for rate-limits and outages, and the ability to A/B test variants without breaking analysis.
**Library:** Recipe `roles[].model_hint` + `model_fallbacks` + `model_experiments` frontmatter → deployed runtime reads it at call time.
**Lives in:** Inline below — recipes declare intent; the deployed project picks per call.

## What it provides

- A **selection rubric** across five axes (quality, latency, cost, cache friendliness, determinism) so picking a model isn't a vibe.
- **Per-role recommendations** for the common role kinds (classifier, specialist, notifier, eligibility, saga step).
- A **fallback-chain convention** the deployed runtime follows when the primary model is throttled, down, or too expensive for the tenant's current budget.
- An **A/B testing convention** with deterministic randomization, so two variants of the same role can run in production without polluting analysis.
- **Per-model caching guidance** so cache hit rate is part of the decision, not an afterthought.

## Why this exists

`agent-scaffold`'s recipe frontmatter accepts `model_hint` per role (PR M4) — but today recipes mostly hard-code Sonnet everywhere, and there's no operational guidance for the deployed project on what to do when the primary model is rate-limited, when the tenant is over budget, or when you want to test Opus vs Sonnet on the `search` role. This doc fills that gap. The fallback + experiment frontmatter described here is the shape the runtime should honour; scaffold will grow first-class support behind it.

## Selection criteria

Five axes. Rank them per role, pick the model whose envelope covers what matters most.

| Axis | What it captures | How to score |
|------|------------------|--------------|
| **Quality required** | Reasoning depth, multi-step coherence, novel-situation handling | Opus > Sonnet > Haiku |
| **Latency budget** | Per-decision wall time the call class can tolerate | Haiku ~0.5s, Sonnet ~2s, Opus ~5s (typical mid-size context) |
| **Cost per call** | USD per call at typical context size | Opus ~5× Sonnet, Sonnet ~10× Haiku ([cost-tracking.md](cost-tracking.md)) |
| **Cache friendliness** | Whether the prefix is stable enough to cache | Long stable system prompts → use more expensive model (cache discount applies); per-request inputs → no cache benefit |
| **Determinism** | How tightly the output must adhere to a schema | Structured output (JSON/tool calls) → Sonnet is often best; open-ended generation → Opus |

Score each axis 1–5 for the role, pick the model whose strengths line up. When two models tie, pick the cheaper one.

## Per-role recommendations

| Role kind | Default model | Why |
|-----------|---------------|-----|
| **Classifier / router** | Sonnet | Structured output, called frequently; doesn't need Opus's depth |
| **Specialist (deep reasoning)** | Opus | Quality matters, low call rate, can afford latency + cost |
| **Notifier / formatter** | Haiku | Template-driven, latency-sensitive, easy task |
| **Eligibility / rules** | Sonnet | Structured + deterministic; rule application is mid-difficulty |
| **Compensation / saga step** | Sonnet | Repeatable, deterministic; reliability over cleverness |
| **Search / candidate ranking** | Opus | Subtle ranking judgments benefit from depth; call rate moderate |
| **Intake / event triage** | Sonnet | Fast classification with a known schema |

This mirrors the rebooking recipe's existing `model_hint` choices (intake=Sonnet, eligibility=Sonnet, search=Opus, notifier=Haiku) — start from this table when drafting a new recipe.

## Fallback chains

Each role declares an ordered list of fallback models. The runtime tries the primary; on a fallback trigger, walks the chain.

```yaml
roles:
  - name: search
    model_hint: opus
    model_fallbacks: [sonnet, haiku]
  - name: intake
    model_hint: sonnet
    model_fallbacks: [haiku]
```

Triggers for falling back to the next model in the chain:

| Trigger | Detection | Recovery |
|---------|-----------|----------|
| **Rate limit (429)** | Anthropic `RateLimitError` | Immediate; try next model |
| **Primary 5xx > N consecutive** | Count failures per (model, window); threshold 3 within 60s | Try next model; reset counter on next success |
| **Tenant over 80% of daily budget (graceful mode)** | See [cost-tracking.md](cost-tracking.md) | Skip primary; route directly to fallback chain until budget resets |
| **Primary not in pricing table** | Lookup miss when computing cost | Hard fail with clear error; never silently call an unpriced model |

### Downgrade semantics

Every fallback decision must be **observable, not silent**:

- Log a `model_routing_downgrade` event with `{role, primary, chosen, reason, request_id, tenant_id}`.
- Attach `model_chosen: "sonnet (fallback from opus, reason=rate_limit)"` to the response envelope returned to the caller.
- Increment `llm_fallback_total{role, primary, chosen, reason}` for the metrics dashboard.
- If the chain exhausts (every model failed), surface a typed `ModelChainExhausted` exception — never just retry the primary forever.

Downstream consumers must check the response envelope and either accept the degraded result or special-case it (e.g., a search ranked by Haiku might need a wider candidate set to compensate for lower quality).

## A/B testing

For experiments, declare them at the recipe level:

```yaml
model_experiments:
  - role: search
    variants: [opus, sonnet]
    split: [50, 50]
    started: 2026-06-01
    stop_after: 2026-07-01
    outcome_metric: customer_acceptance_rate
```

### Deterministic randomization

Per-request randomization **must** be seeded by `(tenant_id, request_id, experiment_name)` — never by `random.random()`. Reasons:

- The same request retried hits the same variant; doesn't pollute analysis.
- A given tenant sees a consistent variant for a session (stickiness without separate session state).
- A/A tests (variant=variant) produce zero divergence, validating the test infra.

```python
import hashlib

def pick_variant(tenant_id: str, request_id: str, experiment: str, variants: list[str], split: list[int]) -> str:
    h = hashlib.sha256(f"{experiment}:{tenant_id}:{request_id}".encode()).digest()
    bucket = int.from_bytes(h[:4], "big") % 100
    acc = 0
    for variant, pct in zip(variants, split, strict=True):
        acc += pct
        if bucket < acc:
            return variant
    return variants[-1]
```

### Outcome tracking + guardrails

- Tag every LLM call with `experiment={name}` and `variant={chosen}` in the cost log.
- Track the outcome metric (quality score, customer acceptance, latency, error rate) per variant.
- **Minimum sample size** before declaring a winner — for binary outcomes (accepted yes/no) at α=0.05 and a 5pp expected lift, you need ~1,000 samples per variant. Refuse to read the dashboard before that.
- **Sequential testing** for early stop — use a method that controls Type-I error under repeated peeking (e.g. mSPRT, alpha-spending). Don't eyeball Grafana every hour and call it.
- **Stop_after** date in the recipe — no experiments running indefinitely without a decision.

## Per-model caching strategy

All three Claude models support prompt caching (5-min ephemeral, 1-hour persistent). The economics are model-dependent.

| Model | Cache read price | Cache write price | Worth caching when prefix > |
|-------|------------------|-------------------|------------------------------|
| Opus | ~10% of input | ~1.25× input | 1,024 tokens (the Anthropic minimum) |
| Sonnet | ~10% of input | ~1.25× input | 1,024 tokens |
| Haiku | ~10% of input | ~1.25× input | 1,024 tokens (rarely worth it — base cost is already low) |

Practical rules:

- **System prompt is always cacheable** for any role called more than a handful of times — stable across requests.
- **Recipe + assembled context** is cacheable as a single ephemeral block for the duration of a session.
- **Per-request user input** is not cacheable — don't try.
- Prefer Opus + caching over Sonnet + no-caching when the cacheable prefix dominates the input — cache hits make Opus 6× cheaper, sometimes flipping the cost comparison.

## Composition

- **With [cost-tracking.md](cost-tracking.md)** — the graceful-degrade enforcement mode reads this routing table to pick the next cheapest model when a tenant approaches their budget. Routing decisions emit the same `tenant_id` + `model_id` + `cost_usd` log line so attribution still works after a downgrade.
- **With [resilience.md](resilience.md)** — a model fallback is a degraded-mode operation in the same family as a circuit-breaker fallback. The Anthropic client should sit inside a per-model breaker so a sustained Opus outage trips the breaker, which then drives the runtime to route everything to Sonnet for the breaker's open window.
- **With [observability.md](observability.md)** — first-class metrics: `llm_calls_total{role, model}`, `llm_fallback_total{role, primary, chosen, reason}`, `llm_experiment_outcomes{name, variant, outcome}`. Surface fallback rate per role on the main agent dashboard — a sudden uptick is the first sign of a primary-model incident.
- **With [audit-logging.md](audit-logging.md)** — changing `model_hint` or starting an experiment is an audited operator action (touches every request that follows). Log `(operator, role, from, to, reason, timestamp)`.

## Tests

- **Per-role default test** — for each role-kind in the recommendation table, assert the recipe's `model_hint` matches the table (or that the recipe documents *why* it deviates).
- **Fallback-trigger test** — mock the Anthropic client to raise `RateLimitError`; assert the next model in `model_fallbacks` is called and `llm_fallback_total{reason="rate_limit"}` increments.
- **Chain-exhaustion test** — mock all models in the chain to fail; assert `ModelChainExhausted` is raised (not silently retried).
- **Deterministic-randomization test** — call `pick_variant` 10,000 times with random `request_id`s; assert the empirical split is within ±2pp of the configured split.
- **A/A test** — configure `variants: [opus, opus]` with `split: [50, 50]`; assert outcome metrics are statistically indistinguishable (validates the test infra).
- **Pricing-gap test** — try to call a model not in `config/anthropic-pricing.json`; assert hard failure, not silent $0 spend.

## Pitfalls

- **Single global model with no fallback** — when Opus rate-limits, the entire system halts. Always declare at least one fallback per role.
- **Hard-coded model in code** — recipe should declare; deployed code reads from config. A model change shouldn't need a code deploy.
- **A/B with per-request `random.random()` randomization** — same request retried may land in a different variant, polluting outcome analysis. Always seed by `(tenant_id, request_id, experiment_name)`.
- **Falling back without lowering quality expectations** — a `notifier` that downgrades Haiku → Haiku is fine; a `search` that downgrades Opus → Haiku may produce visibly worse candidates. Downstream caller must read `model_chosen` from the response envelope.
- **Silent downgrade** — log + metric + response envelope. Without all three, you find out from a customer complaint, not the dashboard.
- **Running an experiment past `stop_after`** — accumulates data forever, no decision is forced, the team loses interest. Bake the stop date into the recipe.
- **Caching per-request user input** — pollutes the cache with single-use prefixes and burns write cost for nothing. Only cache prefixes that recur.
- **Tuning Haiku to match Opus quality** — wastes effort. If the role needs Opus, pay for Opus; if Haiku is good enough, use Haiku as-is.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `roles[].model_hint`: intake=Sonnet (frequent classifier), eligibility=Sonnet (structured rules), search=Opus (subtle ranking), notifier=Haiku (template). Fallback chains and experiments configured at the deployed runtime layer; recipe-level `model_fallbacks` / `model_experiments` will be added when a future PR teaches agent-scaffold to honour them.

## See also

- [`prompt-management.md`](prompt-management.md) — prompt routing follows the same `(tenant_id, request_id)` discipline this doc lays out for model routing. The deterministic-keying primitive applies identically; the runtime can resolve both a model arm and a prompt label from one hash.
