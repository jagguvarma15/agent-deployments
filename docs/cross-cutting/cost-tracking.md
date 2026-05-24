# Cross-cutting: Cost tracking

**Concern:** Attribute LLM + tool costs per tenant, per role, per request — so one chatty tenant can't silently drain the shared budget and so monthly invoices map to actual usage.
**Library:** Structured per-call log + Redis counter (real-time guard) + `costs_daily` Postgres rollup
**Lives in:** Inline below — wire at the LLM-client boundary and every paid-tool call.

## What it provides

- **Per-request attribution** of LLM token usage to a `(tenant_id, agent_role, request_id)` tuple, costed in USD via a versioned pricing table.
- **Three quota types** (per-tenant per-day budget, per-tenant per-request cap, per-tenant rate limit).
- **Three enforcement modes** (soft warn / hard 429 / graceful degrade to a cheaper model).
- **Alerts** at 80% / 100% of daily budget, plus monthly forecast drift.
- **Reporting** — daily per-tenant rollup, monthly CSV invoice, real-time Grafana panel.

## Why this exists

`multi-tenancy.md` covers data isolation (RLS, context propagation) but not cost attribution. In a multi-tenant rebooker, one restaurant chain that triggers ten thousand `check_availability` calls per minute will silently consume the entire shared LLM budget — and you'll find out from the Anthropic invoice, not before. Worse, the cost is hidden inside aggregate metrics: the cluster looks healthy, the consumer lag is fine, but Sonnet spend just doubled.

The fix is attribution: every LLM call carries `tenant_id`, every quota lives at the tenant level, and the cheapest cost ceiling (per-day USD) becomes the back-stop when retries or recursion go wrong.

## What to track

Per LLM call, emit a structured log line with at minimum:

| Field | Source | Why |
|-------|--------|-----|
| `tenant_id` | Context (JWT claim / event envelope) | Attribution and quotas |
| `request_id` | Inbound request / event id | Joins across multi-call workflows |
| `agent_role` | Orchestrator (e.g. `intake`, `eligibility`, `search`, `notifier`) | Costed slice for per-role budgets |
| `model_id` | The actual model called (`claude-sonnet-4-6`, `claude-haiku-4-5-...`) | Pricing lookup |
| `input_tokens` / `output_tokens` | Anthropic `Usage` block | Base cost |
| `cache_read_tokens` / `cache_write_tokens` | Anthropic `Usage` block | Cache discounted/uplifted pricing |
| `thinking_tokens` | Anthropic `Usage.cache_creation_input_tokens` / `thinking` block | Extended-thinking cost — easy to miss |
| `cost_usd` | Computed from the pricing table | Pre-rolled so dashboards don't recompute |
| `latency_ms` | Wall time of the call | Lets you slice cost-per-latency-bucket |

For each paid tool call (Resy/OpenTable/Toast API hit with a per-call price, vector lookup with a $/1k-queries rate, third-party SMS), emit a parallel line:

```json
{"tenant_id": "...", "request_id": "...", "tool": "resy_check_availability",
 "calls": 1, "unit_cost_usd": 0.001, "cost_usd": 0.001}
```

If you only track LLM cost, you'll mis-route quotas — a tenant whose cost is dominated by Resy API calls won't show up in token-only dashboards.

## Where to store

Three tiers, written from the same point but read by different consumers:

1. **Hot path — structured log line** per LLM call, shipped to the log aggregator (see [log-aggregation.md](../stack/log-aggregation.md)). One line per call. JSON, no transformation. This is the source of truth.
2. **Real-time guard — Redis counter** per `(tenant_id, day)` in USD, incremented inside the same code path that emits the log. TTL = 26h (a bit more than a day to handle midnight rollover races). Reset daily by a cron OR rely on TTL + a fresh write on the next call. Consulted *before* every LLM call.
3. **Aggregation — `costs_daily` Postgres table** filled by a nightly job that rolls up the hot-path logs:

```sql
CREATE TABLE costs_daily (
    tenant_id     UUID NOT NULL,
    day           DATE NOT NULL,
    agent_role    TEXT NOT NULL,
    model_id      TEXT NOT NULL,
    requests      BIGINT NOT NULL DEFAULT 0,
    input_tokens  BIGINT NOT NULL DEFAULT 0,
    output_tokens BIGINT NOT NULL DEFAULT 0,
    cache_read    BIGINT NOT NULL DEFAULT 0,
    cache_write   BIGINT NOT NULL DEFAULT 0,
    cost_usd      NUMERIC(12, 4) NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, day, agent_role, model_id)
);
```

Why three tiers: real-time guard is cheap to read on the hot path; the log line is the auditable source of truth; the daily rollup is what monthly invoicing and trend dashboards read.

## Pricing table

Keep a versioned JSON file at `config/anthropic-pricing.json`:

```json
{
  "version": "2026-Q2",
  "effective_from": "2026-04-01",
  "models": {
    "claude-opus-4-7":         {"input_per_1m":  15.00, "output_per_1m":  75.00, "cache_read_per_1m":  1.50, "cache_write_per_1m": 18.75},
    "claude-sonnet-4-6":       {"input_per_1m":   3.00, "output_per_1m":  15.00, "cache_read_per_1m":  0.30, "cache_write_per_1m":  3.75},
    "claude-haiku-4-5-20251001":{"input_per_1m":   1.00, "output_per_1m":   5.00, "cache_read_per_1m":  0.10, "cache_write_per_1m":  1.25}
  }
}
```

Rules:

- **Update quarterly** (or whenever Anthropic publishes new pricing). Commit the change with the effective date; never edit a past entry in place.
- **Include cache prices** — cache reads are typically 10% of input, cache writes are 1.25× — getting this wrong misattributes by 10× either direction.
- **Default to the most expensive variant on lookup miss** so a new model that's not yet in the table can't accidentally appear free.
- **Version the table** in the rolled-up `costs_daily` row (or a sibling column) so historical invoices remain reproducible after the pricing changes.

## Quotas + enforcement

Three quota types. A tenant can have all three; the most restrictive applies.

| Quota | Unit | Typical default | Hot-path cost |
|-------|------|-----------------|---------------|
| **Per-tenant per-day budget** | USD | $50 / day (Tier 1), $500 (Tier 2), unlimited (Enterprise) | One Redis `GET` |
| **Per-tenant per-request cap** | tokens (input + output) | 32,000 | One in-memory check after assembling the request |
| **Per-tenant rate limit** | requests / minute | 60 rpm (Tier 1), 600 rpm (Tier 2) | One Redis `INCR` with EX |

Three enforcement modes, settable per tenant per quota:

- **Soft** — log a `cost_quota_warning` event, continue. Useful for new tenants while you tune their budget.
- **Hard** — return HTTP 429 with `X-RateLimit-Reset` / `X-Cost-Budget-Reset` headers, OR raise a typed `TenantQuotaExceeded` exception inside an event consumer that routes the job to the DLQ (see [dlq-operations.md](dlq-operations.md)).
- **Graceful degrade** — when the tenant is past 80% of their budget, route LLM calls to a cheaper model (Opus → Sonnet → Haiku) per [model-routing.md](#composition). At 100%, fall back to deterministic logic if the recipe supports it (no LLM, just rule-based search), otherwise hard-reject.

```python
async def call_llm(tenant_id: str, role: str, payload: dict) -> Response:
    quota = await load_tenant_quota(tenant_id)
    spent = await redis.get(f"cost:{tenant_id}:{today()}")
    spent_usd = float(spent or 0)

    if spent_usd >= quota.daily_budget_usd:
        if quota.mode == "hard":
            raise TenantQuotaExceeded(tenant_id, spent_usd, quota.daily_budget_usd)
        if quota.mode == "graceful":
            payload = degrade_to_cheaper(payload, current=payload["model"])
        # mode == "soft" → continue, still log the breach

    resp = await anthropic.messages.create(**payload)
    cost = price(payload["model"], resp.usage)
    await redis.incrbyfloat(f"cost:{tenant_id}:{today()}", cost)
    await redis.expire(f"cost:{tenant_id}:{today()}", 26 * 3600)
    log.info("llm_call", tenant_id=tenant_id, role=role, model=payload["model"],
             input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
             cost_usd=cost)
    return resp
```

## Alerts

| Trigger | Tier | Channel |
|---------|------|---------|
| Tenant > 80% of daily budget | Notify | Tenant-managed channel + ops |
| Tenant > 100% of daily budget | Page (if hard mode) / Notify (if soft/graceful) | On-call + tenant |
| Total monthly LLM cost trending > 110% of forecast at any point in the month | Notify | Finance + ops |
| New `model_id` appearing in logs without a pricing-table entry | Page | On-call (likely silent overspend) |
| Cost-per-request P99 spikes > 3× rolling mean | Notify | Ops (likely runaway prompt) |

Surface the metric `llm_cost_usd_total{tenant_id, role, model}` to your metrics exporter; build a Grafana panel showing top 10 tenants by spend, top 10 by spend-trend, and total-vs-forecast.

## Reporting

- **Daily per-tenant cost report** — email or Slack to the tenant's account contact each morning with yesterday's spend, today's quota, and trailing-7-day trend.
- **Monthly invoice attachment** — CSV with `(date, agent_role, model_id, requests, total_tokens, cost_usd)`; one row per `costs_daily` entry filtered to the month and the tenant. The pricing-table version is included in a header row.
- **Real-time dashboard panel** — Grafana with the live `llm_cost_usd_total` metric and the day's budget consumption per tenant. Operators watch this; tenants don't.

## Composition

- **With [multi-tenancy.md](multi-tenancy.md)** — `tenant_id` propagation is a prerequisite. If it's not in the structlog context when the LLM call fires, the cost line is unattributed and quotas can't apply. Bind `tenant_id` at the inbound boundary; assert it's present at the LLM-client boundary.
- **With [observability.md](observability.md)** — emit `llm_cost_usd_total{tenant_id, role, model}` and `llm_tokens_total{kind="input|output|cache_read|cache_write|thinking", tenant_id, model}` as first-class metrics. Cost should be on the same dashboard as latency and error rate.
- **With model-routing** — the graceful-degrade enforcement mode reads the routing table to pick the next cheapest model. When Opus is degraded → Sonnet, the routing logic must also degrade the prompt for the cheaper model (`thinking` off, smaller `max_tokens`).
- **With [backpressure.md](backpressure.md)** — a tenant hitting their cost cap is a backpressure signal: route their work to a slow lane or shed it, don't keep retrying into the quota wall.
- **With [audit-logging.md](audit-logging.md)** — quota-mode changes (`soft → hard`, budget raises) are auditable operator actions. Log `(operator, tenant_id, from_mode, to_mode, reason, timestamp)`.

## Tests

- **Pricing lookup test** — for each entry in the pricing table, assert `price(model, fake_usage)` returns the expected USD; for an unknown model, assert it defaults to the most-expensive entry and emits a warning.
- **Real-time guard test** — exceed the daily budget; assert the next call raises `TenantQuotaExceeded` (hard mode) / routes to cheaper model (graceful) / logs warning (soft).
- **Aggregation test** — feed N synthetic log lines into the nightly rollup; assert `costs_daily` rows match per-tenant totals.
- **Invoice reproducibility test** — re-run the monthly CSV against historical `costs_daily` data and assert it matches the originally-issued invoice byte-for-byte. (This is what catches accidental pricing-table edits.)
- **Per-request cap test** — assemble a request that exceeds `max_tokens_per_request`; assert it's rejected before the LLM call.

## Pitfalls

- **Tracking only the LLM call, not tool costs** — a tenant whose spend is dominated by paid third-party API calls (Resy seat-search at $0.001 each × 100k/day) won't appear in token-only dashboards.
- **Per-account budgets that don't factor in cache hit rate** — same prompt with 95% cache hit is ~6× cheaper. Quotas in raw tokens hide this; always quota on USD.
- **Quotas without graceful degradation** — hard-rejecting an enterprise tenant at 100% budget is worse than silently degrading them to Sonnet. Pick the mode per tier.
- **Editing past entries in the pricing table** — invoice irreproducibility. Always add a new versioned entry; never mutate history.
- **Forgetting `thinking_tokens`** — extended thinking is billed at output rates and can be 5× the visible output. Easy to leave out of the cost computation.
- **Real-time guard out of sync with logs** — if the guard `INCR` happens before the LLM call returns and the call fails, the budget is consumed without work. INCR after a successful response; on retry, the retry-key prevents double-counting.
- **No alert when a new model_id appears** — you ship a new model behind a flag, the pricing table doesn't have it, every call defaults to $0, and you discover the overspend in the invoice. Hard-fail or alert.
- **Per-request token cap without per-day USD cap** — a tenant can stay under per-request limit while making 10× more requests than expected.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — each `(tenant_id, agent_role)` LLM call emits a `llm_call` structlog line with token + cost fields; Redis counter `cost:{tenant_id}:{day}` guards against per-day USD budget breaches; the orchestrator's graceful-degrade mode falls Opus → Sonnet → Haiku as the budget fills.
