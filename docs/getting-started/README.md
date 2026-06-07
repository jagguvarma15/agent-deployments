# Getting started

If you ran `agent-scaffold doctor` and saw a missing or misconfigured service, open the matching guide. Each guide is one screen: signup link at the top, env vars at the bottom, copy-pasteable commands in the middle.

> **Machine-readable index:** This directory's contents are aggregated into the top-level [`catalog.yaml`](../../catalog.yaml). If you're building a tool that consumes this repo, read the catalog rather than walking these files directly. See [`MANIFEST_SCHEMA.md`](../../MANIFEST_SCHEMA.md).

| Service | Required for | Guide |
|---------|--------------|-------|
| Anthropic API | every recipe | [anthropic.md](anthropic.md) |
| Redis | event-driven recipes, caching, rate limiting | [redis.md](redis.md) |
| Postgres | recipes with persistence, LangGraph checkpointing | [postgres.md](postgres.md) |
| Langfuse | LLM observability (optional but recommended) | [langfuse.md](langfuse.md) |
| Kafka | high-throughput event-driven recipes (optional) | [kafka.md](kafka.md) |
| Docker | running local services | [docker.md](docker.md) |
| uv | Python dependency + venv management | [uv.md](uv.md) |
| Keyring | OS-backed secret storage | [keyring.md](keyring.md) |
| Resy | restaurant-rebooking recipe (mock adapter only) | [resy.md](resy.md) |
| OpenTable | restaurant-rebooking recipe (mock adapter only) | [opentable.md](opentable.md) |
| Toast | restaurant-rebooking recipe (mock adapter only) | [toast.md](toast.md) |

## What these are (and aren't)

**These are first-run remediation docs.** Audience: a developer with a working `agent-scaffold doctor` output saying "✗ redis: connection refused" who needs the fastest path to a running service.

**These are not deep references.** For Redis cluster topology, Postgres logical replication, Kafka KRaft tuning, etc., see [`docs/stack/`](../stack/). Each guide here links to its deep-reference sibling.

## Opening from the CLI

```bash
agent-scaffold doctor --explain redis
agent-scaffold doctor --explain anthropic
```

opens the matching guide in `$PAGER`. The CLI bundles a snapshot of this directory, so the docs work offline once `agent-scaffold` is installed.
