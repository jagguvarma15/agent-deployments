---
id: durable.temporal
kind: durable
provides: [durable_workflow, checkpoint_resume, signal_handling]
env_vars: [TEMPORAL_HOST, TEMPORAL_NAMESPACE]
docker:
  service: temporal
  image: temporalio/auto-setup:1.24
  ports: ["7233:7233", "8233:8233"]
  environment:
    DB: postgres12
    DB_PORT: "5432"
    POSTGRES_USER: agent
    POSTGRES_PWD: agent
    POSTGRES_SEEDS: postgres
  depends_on: [postgres]
  healthcheck:
    test: ["CMD-SHELL", "tctl --address temporal:7233 cluster health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
probe: temporal_health
bootstrap_step: bootstrap_temporal
emit_files: []
docs: |
  Temporal OSS as the durable-execution backbone. Agents whose success
  criterion spans hours/days (long-horizon tasks, multi-step approvals,
  external-system waits) declare `durable_workflow: durable.temporal` in
  frontmatter; the scaffold wires the Temporal SDK and emits a worker
  process. Requires `relational.postgres` for Temporal's persistence
  store — the resolver enforces this.
---

# Capability: durable.temporal

> First-run setup: [`getting-started/temporal.md`](../../getting-started/temporal.md). Vendor: https://temporal.io.

**Used for:** Durable execution of long-horizon agent tasks — survives crashes, deploys, and process restarts.

## Why pick this

When the recipe's success criterion is "this completes in 3 days, possibly across 4 deploys, with external waits in the middle." Temporal gives you checkpoint-and-resume, retries with deduplication, signals, queries, and visibility — all the machinery `long_horizon` and `saga` patterns need to be production-real.

`durable.temporal` is the most battle-tested OSS option. SaaS alternatives: `durable.temporal-cloud`. Lighter weight (and less powerful): `durable.inngest` (planned).

## Local setup

The compose fragment above runs Temporal's `auto-setup` image, which auto-creates the keyspaces on first boot using the existing Postgres. Web UI at `http://localhost:8233`.

The bootstrap step `bootstrap_temporal` creates the `default` namespace (or whatever's in `TEMPORAL_NAMESPACE`) if missing.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TEMPORAL_HOST` | `temporal:7233` | Temporal frontend address |
| `TEMPORAL_NAMESPACE` | `default` | Namespace for this agent's workflows |

## Bootstrap

`bootstrap_temporal` runs `tctl namespace register` against the configured namespace. Idempotent — re-runs are no-ops if the namespace exists.

## Cloud / production

- **Temporal Cloud** at https://cloud.temporal.io — managed. Set `TEMPORAL_HOST=<your-namespace>.tmprl.cloud:7233` and provide mTLS certs via env or the SDK config.
- **Self-hosted production** — separate Postgres (or Cassandra), tune retention per namespace, scale workers per task queue.

## When to swap it

- **→ `durable.temporal-cloud`** — same SDK surface, managed control plane.
- **→ `durable.inngest`** — simpler model for shorter workflows, less suited for true long-horizon.

## See also

- [`vendored/blueprints/patterns/long_horizon/overview.md`](../../../vendored/blueprints/patterns/long_horizon/overview.md) — pattern that motivates this capability.
- [`vendored/blueprints/patterns/saga/overview.md`](../../../vendored/blueprints/patterns/saga/overview.md) — sibling pattern with compensation semantics.
