# Cross-cutting: Structured Logging

**Concern:** JSON-structured logs with request/session/user context on every line.
**Library:** `structlog` (Py) / `pino` (TS)
**Lives in:** `common/python/agent_common/logs/` and `common/typescript/src/logging/`

## What it provides

- **One-call setup** -- `configure(service_name, env, log_level)` (Py) / `createLogger(config)` (TS) configures the logger for the entire app.
- **Environment-aware output** -- Development mode renders human-readable colored output. Production mode renders JSON for log aggregators.
- **Contextual binding** -- `structlog.contextvars` (Py) / `pino.child()` (TS) lets you attach request-scoped context (trace ID, user ID, session ID) that appears on every subsequent log line.
- **Standard fields** -- Every log line includes: `service`, `env`, `level`, `timestamp` (ISO 8601), `msg`.

## How to use

### Python

```python
from agent_common.logs import configure
import structlog

# At app startup (typically in lifespan)
configure("docs-rag-qa", env="production", log_level="INFO")

# Get a logger anywhere
logger = structlog.get_logger()

# Basic logging
logger.info("query_received", question="What is MCP?")

# Bind context for a request scope
log = logger.bind(trace_id="abc-123", user_id="user-1")
log.info("processing_query")
log.info("query_answered", citation_count=3)
# Both lines include trace_id and user_id
```

Output (production):

```json
{"service":"docs-rag-qa","env":"production","level":"info","timestamp":"2026-04-27T10:00:00Z","msg":"query_received","question":"What is MCP?"}
```

### TypeScript

```typescript
import { createLogger } from "@agent-deployments/common";

const logger = createLogger({
  serviceName: "docs-rag-qa",
  env: "production",
  level: "info",
});

// Basic logging
logger.info({ question: "What is MCP?" }, "query_received");

// Child logger with request context
const reqLog = logger.child({ traceId: "abc-123", userId: "user-1" });
reqLog.info("processing_query");
reqLog.info({ citationCount: 3 }, "query_answered");
```

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `LOG_LEVEL` | `INFO` | Minimum level to emit (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `APP_ENV` | `development` | Controls output format: `development` = colored console, anything else = JSON |

## Tests

- **Python:** `common/python/tests/test_logging.py` -- configure in both modes, verify output format
- **TypeScript:** `common/typescript/tests/logging.test.ts` -- logger creation, child loggers, level filtering

## Logging conventions

Use these patterns consistently across prototypes:

| Event | Key | Example |
|-------|-----|---------|
| Request received | `{endpoint}_received` | `logger.info("query_received", ...)` |
| Processing step | `{step}_completed` | `logger.info("retrieval_completed", chunk_count=5)` |
| Error | `{operation}_failed` | `logger.error("query_failed", error=str(exc))` |
| External call | `{service}_called` | `logger.info("llm_called", model="claude-sonnet-4-6", tokens=150)` |

Always use **snake_case** event names. Always include the **trace_id** and **user_id** via context binding, not per-call arguments.

## Swapping to OpenTelemetry-native logging

If your deployment already uses an OTel collector:

1. Replace structlog/pino with `opentelemetry-sdk` (Py) / `@opentelemetry/sdk-logs` (TS).
2. Remove the `configure()` / `createLogger()` call.
3. Set `OTEL_EXPORTER_OTLP_ENDPOINT` in env.

This is a **multi-file swap** (common module + app startup + docker-compose for the OTel collector).
