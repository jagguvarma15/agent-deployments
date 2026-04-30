# Cross-cutting: Observability

**Concern:** Trace every LLM call, tool invocation, and agent step so you can debug, optimize, and audit agent behavior.
**Library:** Langfuse (self-hosted, MIT)
**Lives in:** Inline below (formerly `common/python/agent_common/observability/` and `common/typescript/src/observability/`)

## What it provides

- **Singleton client** -- `get_langfuse()` (Py) / `createLangfuseClient()` (TS) initializes once and reuses across the app.
- **Trace decorator** -- `@traced("name")` (Py) / `traced("name", fn)` (TS) wraps any function in a Langfuse trace span with automatic error capture.
- **Async support** -- The Python decorator auto-detects sync vs async functions. The TS version is async-native.
- **Error propagation** -- Exceptions are recorded on the span (level=ERROR, status_message) and re-raised. Tracing never swallows errors.

## How to use

### Python

```python
from agent_common.observability import get_langfuse, traced

# Initialize (typically in app lifespan)
langfuse = get_langfuse(
    public_key="pk-lf-local",
    secret_key="sk-lf-local",
    host="http://localhost:3000",
)

# Trace a function
@traced("answer_question")
async def answer_question(question: str) -> str:
    # LLM call, tool use, etc.
    return result
```

### TypeScript

```typescript
import { createLangfuseClient, traced } from "@agent-deployments/common";

// Initialize
createLangfuseClient({
  publicKey: "pk-lf-local",
  secretKey: "sk-lf-local",
  host: "http://localhost:3000",
});

// Trace a function
const answer = await traced("answer_question", async () => {
  // LLM call, tool use, etc.
  return result;
});
```

### Nesting spans

Create child spans within a traced function for granular visibility:

```python
@traced("rag_pipeline")
async def rag_pipeline(question: str) -> str:
    client = get_langfuse()
    trace = client.trace(name="rag_pipeline")

    # Child span for retrieval
    retrieval_span = trace.span(name="retrieve_chunks")
    chunks = await retrieve(question)
    retrieval_span.end(output=f"{len(chunks)} chunks")

    # Child span for generation
    gen_span = trace.span(name="generate_answer")
    answer = await generate(question, chunks)
    gen_span.end(output=answer[:200])

    return answer
```

## Tests

Test that the observability fixtures work with mocked Langfuse (Py). Test traced() wrapper behavior for both success and error paths (TS).

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `LANGFUSE_PUBLIC_KEY` | `pk-lf-local` | Project public key for the Langfuse API |
| `LANGFUSE_SECRET_KEY` | `sk-lf-local` | Project secret key for the Langfuse API |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse server URL |

These are set in each prototype's `.env.example` and validated at boot via `settings.py` / `config.ts`.

## Viewing traces

With `docker compose up`, Langfuse is available at `http://localhost:3000`:

- Default login: `admin@local.dev` / `admin`
- Project: `default` (auto-created via init env vars in `docker-compose.base.yml`)
- Each request generates a trace with spans for agent steps, tool calls, and LLM invocations

## Swapping to LangSmith

For teams already using LangChain/LangGraph heavily, LangSmith is a drop-in alternative:

1. Replace `langfuse` dependency with `langsmith`
2. Replace `get_langfuse()` / `@traced` with LangSmith's `@traceable` decorator
3. Set `LANGCHAIN_TRACING_V2=true` and `LANGCHAIN_API_KEY` in env
4. Remove Langfuse services from `docker-compose.yml`

This is a **multi-file swap** (common module + env config + docker-compose).

## Reference Implementation

<details>
<summary>Python — <code>langfuse.py</code></summary>

```python
"""Langfuse client singleton and trace decorator."""

import asyncio
import functools
from typing import Any, Callable

from langfuse import Langfuse

_client: Langfuse | None = None


def get_langfuse(
    *,
    public_key: str | None = None,
    secret_key: str | None = None,
    host: str = "http://localhost:3000",
) -> Langfuse:
    """Get or create the Langfuse singleton client."""
    global _client
    if _client is None:
        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    return _client


def traced(
    name: str | None = None,
    *,
    metadata: dict[str, Any] | None = None,
) -> Callable:
    """Decorator that wraps a function in a Langfuse trace span."""

    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__name__

        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_langfuse()
            trace = client.trace(name=span_name, metadata=metadata or {})
            span = trace.span(name=span_name)
            try:
                result = await fn(*args, **kwargs)
                span.end(output=str(result)[:500])
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            client = get_langfuse()
            trace = client.trace(name=span_name, metadata=metadata or {})
            span = trace.span(name=span_name)
            try:
                result = fn(*args, **kwargs)
                span.end(output=str(result)[:500])
                return result
            except Exception as exc:
                span.end(level="ERROR", status_message=str(exc))
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper
        return sync_wrapper

    return decorator
```

</details>

<details>
<summary>TypeScript — <code>langfuse.ts</code></summary>

```typescript
/**
 * Langfuse client wrapper and trace utilities.
 *
 * Note: This is a lightweight wrapper. The actual Langfuse SDK should be
 * installed in each prototype that needs it. This module provides the
 * configuration shape and a traced() helper pattern.
 */

export interface LangfuseConfig {
  publicKey: string;
  secretKey: string;
  host?: string;
}

interface TraceSpan {
  name: string;
  startTime: number;
  endTime?: number;
  metadata?: Record<string, unknown>;
  status?: "ok" | "error";
  error?: string;
}

let _config: LangfuseConfig | null = null;

/**
 * Initialize the Langfuse client configuration.
 */
export function createLangfuseClient(config: LangfuseConfig): LangfuseConfig {
  _config = config;
  return _config;
}

/**
 * Decorator-style wrapper that traces a function execution.
 *
 * Usage:
 *   const result = await traced("my-operation", async () => {
 *     return doSomething();
 *   });
 */
export async function traced<T>(
  name: string,
  fn: () => Promise<T>,
  metadata?: Record<string, unknown>,
): Promise<T> {
  const span: TraceSpan = {
    name,
    startTime: Date.now(),
    metadata,
  };

  try {
    const result = await fn();
    span.endTime = Date.now();
    span.status = "ok";
    return result;
  } catch (error) {
    span.endTime = Date.now();
    span.status = "error";
    span.error = error instanceof Error ? error.message : String(error);
    throw error;
  }
}
```

</details>
