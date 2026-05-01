# Stack pick: Langfuse

**Choice:** Langfuse 2.95, self-hosted via Docker (MIT-licensed)
**Used for:** LLM observability -- tracing agent steps, tool calls, LLM invocations, latency, cost

## Why this over alternatives

| Option | Why not |
|--------|---------|
| LangSmith | Excellent for LangChain teams, but proprietary and not self-hostable. Available as a swap for LangGraph prototypes |
| Helicone | Proxy-based tracing; less granular than SDK-level instrumentation |
| Braintrust | Strong eval focus but less mature on tracing |
| Raw OpenTelemetry | Requires more setup; Langfuse provides an agent-specific UI out of the box |

Langfuse was chosen because it's open-source, self-hostable, framework-agnostic, and has native support for LLM-specific concepts (traces, generations, scores).

## Local setup

Langfuse requires Postgres (shared), ClickHouse, and MinIO. All defined in the [Docker Compose template](../reference/docker-compose-template.md):

```yaml
langfuse-clickhouse:
  image: clickhouse/clickhouse-server:24
  environment:
    CLICKHOUSE_DB: langfuse
    CLICKHOUSE_USER: langfuse
    CLICKHOUSE_PASSWORD: langfuse

langfuse-minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"

langfuse:
  image: langfuse/langfuse:2
  ports:
    - "${LANGFUSE_PORT:-3000}:3000"
  depends_on:
    postgres: { condition: service_healthy }
    langfuse-clickhouse: { condition: service_healthy }
    langfuse-minio: { condition: service_started }
```

After `docker compose up`, open `http://localhost:3000`:
- Login: `admin@local.dev` / `admin`
- Project: `default` (auto-created)

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| `LANGFUSE_PORT` | `3000` | Langfuse UI port |
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-local` | Project public key for SDK clients |
| `LANGFUSE_SECRET_KEY` | `sk-lf-local` | Project secret key for SDK clients |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse API URL |
| `LANGFUSE_SECRET` / `NEXTAUTH_SECRET` | `mysecret` | Auth secret for Langfuse web UI |

## Integration pattern

See [cross-cutting/observability.md](../cross-cutting/observability.md) for the SDK integration code (Python `@traced` decorator, TypeScript `traced()` wrapper).

### Quick reference

```python
# Python
from agent_common.observability import get_langfuse, traced

langfuse = get_langfuse(public_key="pk-lf-local", secret_key="sk-lf-local")

@traced("answer_question")
async def answer_question(q: str) -> str:
    ...
```

```typescript
// TypeScript
import { createLangfuseClient, traced } from "@agent-deployments/common";

createLangfuseClient({ publicKey: "pk-lf-local", secretKey: "sk-lf-local" });

const answer = await traced("answer_question", async () => { ... });
```

## What you see in the UI

Each agent request creates a trace with:

- **Root span** -- the full request lifecycle
- **Child spans** -- retrieval, generation, tool calls
- **Generation details** -- model, token counts, latency, cost
- **Scores** -- attach eval scores to traces for quality monitoring

## Where used in repo

- **[Observability cross-cutting doc](../cross-cutting/observability.md)** -- Langfuse client wrapper and `@traced` decorator (with reference implementation)
- **[Docker Compose template](../reference/docker-compose-template.md)** -- Langfuse + ClickHouse + MinIO services
- **Every blueprint** -- traces agent execution via the observability module
- **Settings** -- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` in each `.env.example`

## Swapping to LangSmith

For teams using LangChain/LangGraph:

1. Replace `langfuse` dependency with `langsmith`.
2. Replace `@traced` with LangSmith's `@traceable` decorator.
3. Set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY`.
4. Remove Langfuse, ClickHouse, and MinIO services from docker-compose.

This is a **multi-file swap** (common module + env config + docker-compose).
