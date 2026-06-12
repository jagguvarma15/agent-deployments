---
tags: [background-jobs, queue-workers]
when_to_load: "recipe needs background processing"
---

# Stack pick: Background jobs

**Choice (Py):** Celery 5.x with a Redis broker (or RabbitMQ); Dramatiq for simpler workloads
**Choice (TS):** BullMQ 5.x with Redis
**Used for:** Long-running tasks, scheduled / recurring jobs, retries with backoff, work that shouldn't block an HTTP request

## When to use background jobs

- Work that takes longer than an HTTP request should (> 5 s).
- Scheduled / recurring tasks (nightly aggregations, weekly reports).
- Work triggered by an HTTP request that does heavy I/O or CPU.
- Tasks that need retry-with-backoff (sending email, calling flaky third-party APIs).
- Decoupling user requests from heavy work — enqueue and respond immediately.

## When NOT to use them

- **Real-time event handling.** Use [event-driven](../patterns/event-driven.md) consumer loops (Redis Streams / Kafka); they're shaped for that workload.
- **Very short tasks** (< 100 ms). Broker overhead exceeds the savings.
- **One-off batch jobs** that fit in a CLI script.
- **At-most-once mission-critical work.** Background-job systems are at-least-once by design; pair with idempotency or pick a different tool.

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Celery (Py) | Mature; battle-tested; rich features (chord, group, beat); complex ergonomics |
| Dramatiq (Py) | Simpler than Celery; better defaults; smaller ecosystem |
| RQ (Py) | Minimal; good for simple cases; weaker scheduling |
| Cron + script | Fine for true one-off scheduled jobs; doesn't scale |
| BullMQ (TS) | De facto standard for Node async jobs; great dashboard via `bull-board` |
| Bree (TS) | Cron-style; lighter than BullMQ |
| Cloud-managed (AWS SQS + Lambda, GCP Cloud Tasks) | Less ops; vendor lock-in |
| Temporal | Workflow engine; overkill for plain background jobs but the right answer for long-running, stateful workflows |

For mise: Celery with Redis broker for Python services; BullMQ if any TypeScript service needs jobs.

## Celery setup (Python)

```python
# tasks.py
import httpx
from celery import Celery
from celery.schedules import crontab

app = Celery(
    "rebooking",
    broker="redis://redis:6379/1",
    backend="redis://redis:6379/2",        # result backend; optional but useful
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,                   # ack after success, not on receive
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,          # one task at a time per worker
    task_default_retry_delay=60,
    task_default_max_retries=5,
    task_track_started=True,
    worker_max_tasks_per_child=500,        # rotate workers to bound memory leaks
)

@app.task(
    bind=True,
    autoretry_for=(httpx.ConnectError, httpx.TimeoutException),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def send_email_notification(self, idempotency_key: str, customer_id: str, template: str, context: dict) -> None:
    if redis.set(f"email:idem:{idempotency_key}", "claimed", ex=60, nx=True) is None:
        return                              # duplicate; another worker handled it
    try:
        customer = fetch_customer(customer_id)
        rendered = render(template, context)
        email_provider.send(customer.email, rendered)
        redis.set(f"email:idem:{idempotency_key}", "done", ex=86400)
    except Exception:
        redis.delete(f"email:idem:{idempotency_key}")
        raise

# Beat schedule (cron-style)
app.conf.beat_schedule = {
    "nightly-dlq-summary": {
        "task": "tasks.email_dlq_summary",
        "schedule": crontab(hour=2, minute=0),
    },
}
```

Run the components:

```bash
celery -A tasks worker --loglevel=info --concurrency=4
celery -A tasks beat --loglevel=info
celery -A tasks flower                       # web UI on :5555
```

## BullMQ setup (TypeScript)

```typescript
import { Queue, Worker } from "bullmq";
import IORedis from "ioredis";

const connection = new IORedis({
  host: "redis",
  port: 6379,
  maxRetriesPerRequest: null,                // required by BullMQ
});

export const emailQueue = new Queue("emails", { connection });

new Worker(
  "emails",
  async (job) => {
    const { idempotency_key, customer_id, template, context } = job.data;
    const claimed = await redis.set(`email:idem:${idempotency_key}`, "claimed", "EX", 60, "NX");
    if (!claimed) return;                    // dedupe

    try {
      const customer = await fetchCustomer(customer_id);
      const rendered = render(template, context);
      await emailProvider.send(customer.email, rendered);
      await redis.set(`email:idem:${idempotency_key}`, "done", "EX", 86400);
    } catch (err) {
      await redis.del(`email:idem:${idempotency_key}`);
      throw err;
    }
  },
  { connection, concurrency: 4 },
);

// Enqueue
await emailQueue.add(
  "send",
  { idempotency_key: "evt-abc:notify", customer_id: "c-1", template: "rebooked", context: { time: "19:30" } },
  {
    attempts: 5,
    backoff: { type: "exponential", delay: 1000 },
    removeOnComplete: { age: 86400 },
    removeOnFail: false,
  },
);

// Repeatable / scheduled (cron-style)
await emailQueue.add(
  "nightly-summary",
  {},
  { repeat: { pattern: "0 2 * * *", tz: "UTC" } },
);
```

## Idempotency in jobs

Background jobs are at-least-once. Same pattern as event handlers — see [idempotency.md](../cross-cutting/idempotency.md). The snippets above use two-phase claim/release; for write-then-read paths the single-phase SETNX variant is fine.

Always pass the idempotency key as an explicit job argument — don't derive it from the job-id, because retries re-use the job-id while the *intended action* should be idempotent.

## Retry & DLQ

### Celery

```python
@app.task(
    bind=True,
    autoretry_for=(httpx.ConnectError, httpx.TimeoutException),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=5,
)
def call_platform(self, *args, **kwargs):
    try:
        do_work(*args, **kwargs)
    except PermanentError as e:
        app.send_task("tasks.dlq", args=[self.request.id, args, kwargs, str(e)])
        return                                # don't retry; DLQ'd
```

### BullMQ

BullMQ has built-in `failed` retention. A dedicated DLQ queue is the manual pattern:

```typescript
worker.on("failed", async (job, err) => {
  if (job && job.attemptsMade >= (job.opts.attempts ?? 1)) {
    await dlqQueue.add("dlq", {
      original: job.data,
      error: err.message,
      attempts: job.attemptsMade,
    });
  }
});
```

Alert on DLQ depth and DLQ insertion rate (see [prometheus-grafana.md](./prometheus-grafana.md)).

## Scheduling patterns

| Need | Celery | BullMQ |
|------|--------|--------|
| Cron-style recurring | `beat_schedule` with `crontab(...)` | `repeat: { pattern: "..." }` |
| Delayed (one-time) | `apply_async(countdown=60)` | `{ delay: 60_000 }` |
| Periodic (every N seconds) | `schedule: 60.0` in beat | `repeat: { every: 60_000 }` |

For high-reliability scheduling, **don't rely on a single `beat` pod**. Either:
- Run `celery beat` with leader election (`celery-redbeat` uses Redis-based locking).
- Replace with a dedicated workflow engine (Temporal, Apache Airflow) for anything beyond simple cron.

## Observability

| Stack | What it gives you |
|-------|-------------------|
| Celery + `flower` | Web UI for task inspection, retries, rates |
| Celery + `celery-prometheus-exporter` | Prometheus metrics for task counts, latencies, queue depth |
| BullMQ + `bull-board` | Web UI per-queue; jobs / failed / completed views |
| BullMQ + custom OTel | Instrument `on('completed'|'failed'|'stalled')` |

Always log per task: task id, args (PII-redacted), duration, outcome, attempt number. See [audit-logging.md](../cross-cutting/audit-logging.md) for the audit-vs-application-log distinction.

## Pitfalls

- **Worker prefetch too high** — one long-running task hoards prefetched jobs; others wait. `worker_prefetch_multiplier=1` for variable-duration workloads.
- **No idempotency** — retries cause duplicate side effects (double-send emails, double-charges).
- **Large payloads in job args** — broker memory grows unbounded; pass IDs and fetch the row from the DB inside the worker.
- **Using Celery as a synchronous service** (`result.get(timeout=...)`) — defeats the purpose; if you need RPC, use RPC.
- **No DLQ** — failed jobs lost on max retries; debugging is forensic at best.
- **`beat` without HA** — schedule stops on single-pod failure; use `celery-redbeat` or move to a dedicated scheduler.
- **No `worker_max_tasks_per_child`** — Python worker leaks accumulate; OOM eventually.
- **Ack-late but task does multiple side effects** — partial-completion retry double-effects.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — primary path is event-driven; background jobs cover scheduled summaries and outbound notification retries.
- Future mise/ops recommendation engine — periodic recompute jobs.

## Production considerations

- **Worker autoscaling** — KEDA on queue depth (Redis-list length or BullMQ stream metric); see [kubernetes-helm.md](./kubernetes-helm.md).
- **Broker HA** — Redis Sentinel or Redis cluster mode; RabbitMQ cluster with quorum queues.
- **Long-running tasks** — set visibility timeout / ack-deadline above task p99; otherwise the broker redelivers mid-work.
- **Memory** — rotate workers via `worker_max_tasks_per_child` to bound Python-side leaks; pair with container memory limits.
- **Result backend retention** — successful task results expire; configure TTL so the result backend doesn't grow forever.

## See also

- `cross-cutting/idempotency.md` — every job handler that mutates state should be idempotent.
- `cross-cutting/event-driven` pattern via `patterns/event-driven.md` — for real-time event handling, prefer that path.
- `cross-cutting/audit-logging.md` — log job lifecycle events into the application log; mutations into the audit log.
- `kubernetes-helm.md` — KEDA-driven worker autoscaling on queue depth.
- `prometheus-grafana.md` — DLQ rate + queue-depth alerts.
