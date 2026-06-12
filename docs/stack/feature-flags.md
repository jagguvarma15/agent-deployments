---
tags: [feature-flags, rollout]
when_to_load: "recipe needs runtime configuration toggles"
---

# Stack pick: Feature flags

**Choice:** GrowthBook (open-source, self-hostable) OR LaunchDarkly (managed; gold standard) OR Unleash (open-source; mature)
**Used for:** Gradual rollouts, A/B testing, kill switches, per-tenant configuration, dark launches

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Environment variables | OK for static boolean flags; no rollout %, no targeting, no runtime change |
| Config files + redeploy | Slow; can't flip a kill switch in seconds |
| Feature-flag service (LD / GrowthBook / Unleash) | Real flags: targeting, percentage rollouts, audit log, SDK with caching |
| Database table | Workable build-your-own; missing UI, SDK, and audit |
| Cloud-native (AWS AppConfig, Firebase Remote Config) | Cheap; less expressive than dedicated flag services |

For mise:

- **Start with GrowthBook self-hosted** — free, full features, A/B testing built in.
- **Migrate to LaunchDarkly** when team needs tooling maturity beyond what self-hosted gives.
- **Unleash** is a solid open-source alternative; simpler than GrowthBook, less analytics.

## Four categories of flags

| Category | Example | Lifetime |
|----------|---------|----------|
| **Release** | "enable new rebooking algorithm" | Weeks — delete once at 100% |
| **Experiment** | "A/B test: greedy vs LLM-decided rebooking" | Weeks — delete when experiment concludes |
| **Permission / config** | "premium-tier features", per-tenant toggles | Permanent — lives as configuration |
| **Ops / kill switch** | "disable third-party API calls", "fall back to cache only" | Permanent — rare use, very high value |

**Discipline:** every release / experiment flag MUST have a delete date. Old release flags are technical debt that silently complicates every code path that branches on them.

## GrowthBook setup (self-hosted)

```yaml
growthbook-mongo:
  image: mongo:6
  volumes:
    - growthbook-data:/data/db

growthbook:
  image: growthbook/growthbook:latest
  depends_on: [growthbook-mongo]
  environment:
    MONGODB_URI: mongodb://growthbook-mongo:27017/growthbook
    JWT_SECRET: <generated>
    APP_ORIGIN:  http://localhost:3002
    API_HOST:    http://localhost:3100
  ports:
    - "3002:3000"      # UI
    - "3100:3100"      # SDK endpoint
```

The UI gives you flag CRUD, targeting rules, experiment setup, and an audit log of changes.

## Python integration

```python
from growthbook import GrowthBook

gb = GrowthBook(
    api_host="http://growthbook:3100",
    client_key="sdk-key-here",
    enabled=True,
)
# In a long-running service, refresh feature definitions once at boot and on a timer.
gb.load_features()

async def handle_event(event):
    gb.set_attributes({
        "restaurant_id": str(event.restaurant_id),       # stable id → sticky bucketing
        "tier":          await fetch_tenant_tier(event.restaurant_id),
        "env":           settings.app_env,
    })

    if gb.is_on("use_llm_rebooking"):
        decision = await llm_decide(event)
    else:
        decision = greedy_decide(event)
```

### SDK caching

The SDK caches feature definitions in memory and refreshes every N seconds (default 60). Flag changes take effect within ~1 minute — fine for non-emergency rollouts.

For kill switches needing < 1 s propagation, GrowthBook supports SSE (server-sent events) for push updates. Fallback if you can't enable SSE: a Redis-backed flag with pub/sub.

## TypeScript integration

```typescript
import { GrowthBook } from "@growthbook/growthbook";

const gb = new GrowthBook({
  apiHost: "http://growthbook:3100",
  clientKey: "sdk-key-here",
  enableDevMode: process.env.NODE_ENV !== "production",
});

await gb.init();

gb.setAttributes({
  restaurant_id: event.restaurant_id,
  tier:          await fetchTier(event.restaurant_id),
});

if (gb.isOn("use_llm_rebooking")) {
  // new path
}
```

## Targeting

GrowthBook (and LaunchDarkly / Unleash) support attribute-based targeting:

- **Boolean** — on / off for everyone.
- **Percentage rollout** — on for 10% of `restaurant_id`s, with sticky bucketing.
- **Attribute filter** — on for `tier == "premium" AND region == "us-east"`.
- **A/B variants** — split by `restaurant_id` hash into variants with weights.

### Sticky bucketing

Always include a stable identifier (`restaurant_id`, `customer_id`) in attributes. The SDK hashes it deterministically — the same restaurant always lands in the same bucket. Without a stable identifier the bucket flips on every request and the rollout is meaningless.

## Kill switches

Flags whose ON state disables a feature entirely. Use for:

- Third-party API outage — skip API calls; return cached / mock data.
- Performance issue — disable an expensive feature in seconds.
- Security incident — disable an affected code path without redeploying.

Wire ops alerts to kill-switch flips; document each kill switch's intent in the flag description. Test the kill path on a cadence — a kill switch that's never been flipped is rarely the kill switch you think it is.

## Per-tenant configuration

Permission / config flags fit naturally on top of multi-tenancy. Use the tenant ID as the bucketing key; combine with targeting rules:

```python
gb.set_attributes({"restaurant_id": str(tenant_id), "tier": tier})
if gb.is_on("multi_chef_view"):
    return new_view(...)
```

See [multi-tenancy.md](../cross-cutting/multi-tenancy.md) for the broader tenant-context propagation pattern; feature flags are one of the cleanest places to express per-tenant toggles.

## Auditing flag changes

Every flag service has a change log. Treat it like an audit log: who flipped which flag, when, why. Mirror critical flips (kill switches, permission flags) into your application audit log — see [audit-logging.md](../cross-cutting/audit-logging.md).

## A/B testing

Pair feature flags with metrics tracking:

```python
variant = gb.get_feature_value("rebooking_algorithm", "control")  # "control" | "treatment"

decision = run_variant(variant, event)

metrics.counter(
    "rebooking_outcome_total",
    labels={"variant": variant, "action": decision.action.value},
).inc()
```

GrowthBook can ingest the metric stream and tell you which variant wins (it integrates with several analytics backends — Postgres, BigQuery, Mixpanel). LaunchDarkly has equivalent integrations via Experiments.

## Flag lifecycle

| State | Action |
|-------|--------|
| Proposed | Issue / ticket open; not yet implemented |
| Active | In code; toggle visible in UI |
| Rolled out | At 100%; schedule removal |
| Removed | Code path deleted; flag deleted |

Run a quarterly "flag cleanup": delete release flags older than 90 days that are at 100%. Keep the count of active release flags as a tracked metric — it tells you if cleanup is keeping up with new flag introduction.

## Pitfalls

- **Forgotten release flags accumulate** — dead code paths the compiler can't help you find.
- **No stable bucketing attribute** — rollout flips per-request; not actually a rollout.
- **Flag eval in a hot loop without caching** — API hammering, latency spikes.
- **Defaults that don't fail safe** — flag service unreachable → undefined behavior. Default to "current behavior" or "feature off" depending on the flag's purpose.
- **Storing PII in attributes** — attributes are sent to the flag service; they're not the place for emails or names.
- **Different flag names for the same concept across services** — coordination chaos; pick one canonical name in the flag service.
- **Treating the flag service as a data store** — it's a configuration plane; data belongs in the DB.
- **Kill switches with no test path** — the first time you flip it in production is a bad time to find a bug.

## Where used in repo

- Future mise/ops recommendation engine — A/B between strategies.
- Future mise/rebooking — feature-gating new algorithms before full rollout.
- Per-tenant config — see [multi-tenancy.md](../cross-cutting/multi-tenancy.md).

## Production considerations

- **Safe defaults in the SDK** — fail closed for risky features (new + untested → off), fail open for benign defaults (existing behavior).
- **Local cache fallback** — cache feature definitions to a local file so the service starts even if the flag backend is down.
- **Self-hosted HA** — SDK endpoint and UI both need HA; back the underlying Mongo / Postgres up. The flag-service outage is a *latent* outage of every guarded feature.
- **Managed cost** — LaunchDarkly pricing scales with seats / MAU; budget accordingly. GrowthBook self-hosted has no per-seat cost.
- **Audit access to the UI** — flag flips can break production faster than code changes; SSO + RBAC + change log review.

## See also

- `cross-cutting/multi-tenancy.md` — per-tenant feature toggles ride on tenant attribute propagation.
- `cross-cutting/audit-logging.md` — mirror critical flag flips into the audit log.
- `cross-cutting/observability.md` — combine flag variant labels with metrics to measure rollout impact.
