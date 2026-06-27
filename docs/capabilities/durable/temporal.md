---
id: durable.temporal
kind: durable
implements:
  port: durable
  interface_version: "1.0"
layer: agent
requires: [relational.postgres]
bootstrap_inputs:
  database_name: temporal
  namespace_name: default
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
provisioning_time: ~60s
cost_tier: free
est_tokens: 750
card:
  name: Temporal OSS
  description: "Durable-execution workflow engine for long-horizon agent tasks with checkpoint-resume, signals, and visibility."
  capabilities_provided: [durable_workflow, checkpoint_resume, signal_handling, retry_with_dedup]
  required_credentials: []
emit_files: []
docs: |
  Temporal OSS as the durable-execution backbone. Agents whose success
  criterion spans hours/days declare `durable_workflow: durable.temporal`
  in frontmatter; the scaffold wires the Temporal SDK and emits a worker
  process. Requires `relational.postgres` for Temporal's persistence store.
tags: [durable, workflow-engine, long-running]
when_to_load: "recipe declares durable.temporal"
verification:
  tier: T1
---

# Capability: durable.temporal

> First-run setup: [`getting-started/temporal.md`](../../getting-started/temporal.md). Vendor: https://temporal.io.

**Used for:** Durable execution of long-horizon agent tasks — survives crashes, deploys, and process restarts. Provides checkpoint-and-resume, retries with deduplication, signals, queries, and visibility.

## Local setup

The compose fragment runs Temporal's `auto-setup` image, which auto-creates the keyspaces on first boot using the existing Postgres. Web UI at `http://localhost:8233`.

`bootstrap_temporal` creates the `default` namespace (or whatever's in `TEMPORAL_NAMESPACE`) if missing.

## Bootstrap (post docker_up)

```bash
tctl --address temporal:7233 namespace register default --retention 1
```

Idempotent — re-runs are no-ops if the namespace exists.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TEMPORAL_HOST` | `temporal:7233` | Temporal frontend address |
| `TEMPORAL_NAMESPACE` | `default` | Namespace for this agent's workflows |

## Client integration

**Python (temporalio):**

```python
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity

@activity.defn
async def call_llm(prompt: str) -> str:
    return await llm.complete(prompt)

@workflow.defn
class ResearchWorkflow:
    @workflow.run
    async def run(self, question: str) -> str:
        # Survives worker restarts; resumes from checkpoint
        plan = await workflow.execute_activity(call_llm, f"Plan: {question}",
                                                schedule_to_close_timeout=timedelta(minutes=5))
        return await workflow.execute_activity(call_llm, f"Execute: {plan}",
                                                schedule_to_close_timeout=timedelta(minutes=30))

# Worker (runs in its own process)
async def main():
    client = await Client.connect(os.environ["TEMPORAL_HOST"], namespace=os.environ["TEMPORAL_NAMESPACE"])
    worker = Worker(client, task_queue="research", workflows=[ResearchWorkflow], activities=[call_llm])
    await worker.run()
```

**TypeScript (@temporalio/client + @temporalio/worker):**

```ts
import { Client, Connection } from "@temporalio/client";
import { Worker, NativeConnection } from "@temporalio/worker";

const connection = await Connection.connect({ address: process.env.TEMPORAL_HOST! });
const client = new Client({ connection, namespace: process.env.TEMPORAL_NAMESPACE });

const handle = await client.workflow.start("researchWorkflow", {
  taskQueue: "research",
  workflowId: `research-${Date.now()}`,
  args: ["compare GraphQL vs gRPC"],
});
const result = await handle.result();
```

## Cloud / production

- **Temporal Cloud** at https://cloud.temporal.io — managed. Set `TEMPORAL_HOST=<namespace>.tmprl.cloud:7233` and provide mTLS certs via env or SDK config.
- **Self-hosted production** — separate Postgres (or Cassandra), tune retention per namespace, scale workers per task queue.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Namespace default not found` | Bootstrap step didn't run | Run `tctl namespace register default --retention 1` manually |
| Worker pod crashes on start | `TEMPORAL_HOST` unreachable | Check compose service name + network; default is `temporal:7233` in compose |
| `cluster unavailable` | Postgres for Temporal not ready | `docker compose logs postgres` — wait for "ready to accept connections" |
| Workflow stuck in "Started" | No worker polling the task queue | Run a worker for that task queue; verify via Web UI |

## See also

- [`patterns/long_horizon/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/long_horizon/overview.md) — pattern motivating this capability
- [`patterns/saga/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/saga/overview.md) — sibling pattern with compensation
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
