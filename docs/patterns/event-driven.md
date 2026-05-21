# Pattern: Event-Driven Agents

**One-liner:** Agents triggered by queue or stream events instead of HTTP requests. Subscribe → receive → enrich → decide → act → ACK.

> **Canonical reference:** [agent-blueprints/patterns/event-driven](https://github.com/jagguvarma15/agent-blueprints/tree/main/patterns/event-driven) — deeper architecture, design tradeoffs, and implementation guidance.

## When to use

- The trigger is an external event (cancellation, status change, scheduled job), not a user request.
- The agent must react in near-real-time but no human is waiting synchronously for the response.
- Multiple downstream consumers may need to react to the same event.
- You need durable replay for backfills or new agents.

## When NOT to use

- The user is waiting synchronously for the answer.
- Event rate is <1/min and a polling cron would suffice.
- The agent's tool calls cannot be made idempotent.

## Core flow

```
Event source (Redis Streams / Kafka / SQS / NATS)
    |
    v
[Consumer group: one or more workers pull events]
    |
    v
[Idempotency check] -- duplicate? --> ACK and exit
    |
    v
[Agent loop: enrich state via tools, decide, act]
    |
    ├── success ──> emit outcome event + persist state + ACK
    └── failure ──> retry with backoff; after N attempts, DLQ
```

### Variants

- **Single consumer:** one worker per stream; simple, no horizontal scale.
- **Consumer group:** multiple workers, partition-keyed for ordering within a key.
- **Event sourcing:** agent state rebuilt entirely from event log replay.
- **Trigger-only:** event is a "go look at the world" signal; agent re-fetches current state via tools rather than trusting the event payload.

## Key components

- **Event source:** Redis Streams (default for ≤10k events/sec), Kafka, SQS, NATS JetStream.
- **Consumer:** Pulls events, dispatches to handler, manages ACK lifecycle.
- **Idempotency store:** Redis SET with TTL, or Postgres unique constraint on event_id.
- **Agent handler:** Receives event, runs reasoning loop, calls tools.
- **Outcome emitter:** Persists decision + emits follow-up event (optional).
- **DLQ:** Separate stream for poison events after N retry attempts.

## Common pitfalls

- **Forgetting idempotency:** at-least-once delivery means duplicates are normal. Every action-taking tool must be idempotent or the agent must dedupe.
- **TTL < retention window:** idempotency store expires before the event source replays — duplicates slip through.
- **Partition key too coarse:** all events queue behind one worker, no parallelism.
- **Partition key too fine:** related events processed out of order (e.g., cancellation processed before the original booking).
- **DLQ alarms missing:** poison events accumulate silently. Alert on DLQ depth.
- **Polling-shaped code on event-driven infra:** code that re-fetches every N seconds inside the handler defeats the point.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | State machine maps cleanly to event-driven lifecycle | Best fit — explicit state, easy to wire to consumer loop |
| Pydantic AI | No event source primitives; agent runs inside your consumer | Works; you write the consumer loop yourself |
| CrewAI | Designed for collaborative crews, not event consumers | Awkward fit |
| Mastra | Workflows can be event-triggered | TS-native option |
| Vercel AI SDK | No event source primitives | Works in TS but you build the loop |

## Stack components needed

- **Event source:** [Redis Streams](../stack/cache-redis.md#redis-streams-as-event-source) (in this repo), Kafka, or SQS.
- **Idempotency:** [Redis](../stack/cache-redis.md) or [Postgres](../stack/relational-postgres.md).
- **State persistence:** [Postgres](../stack/relational-postgres.md) for outcomes; optional Redis for transient state.
- **Tracing:** [Langfuse](../stack/tracing-langfuse.md) — propagate trace_id from event payload through tool calls.

## Reference implementations

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — real-time rebooking agent triggered by reservation cancellation events (LangGraph + Redis Streams).
