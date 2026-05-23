# Stack pick: Log aggregation

**Choice:** Loki (Grafana stack) for self-hosted; Datadog / Better Stack / Axiom for managed
**Used for:** Centralized search across structured logs from every service instance; correlation with traces via `trace_id`

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| ELK (Elasticsearch + Logstash + Kibana) | Heavy operational footprint; license complexity post-Elastic relicense (Elastic 2.0 vs Apache 2.0) |
| Loki + Grafana | Cheap (object-storage backend); index-on-labels not on content; pairs with Grafana you already run |
| Datadog Logs | Managed; powerful; expensive at scale (~$1.27 / GB ingested + retention) |
| CloudWatch Logs | Default if on AWS; clunky query UI; CloudWatch Insights is fine but pricey |
| Better Stack / Axiom | Modern managed; reasonable pricing; good DX |
| stdout to `docker logs` | Acceptable for a single-pod prototype; doesn't scale, doesn't survive container restarts |

For mise: Loki self-hosted in dev / single-region prod; switch to Grafana Cloud Loki or Datadog when ops bandwidth becomes the constraint or you grow into multi-region.

## Local setup

```yaml
loki:
  image: grafana/loki:latest
  command: -config.file=/etc/loki/local-config.yaml
  ports: ["3100:3100"]
  volumes:
    - loki_data:/loki

promtail:
  image: grafana/promtail:latest
  volumes:
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - ./promtail-config.yml:/etc/promtail/config.yml
  command: -config.file=/etc/promtail/config.yml
  depends_on: [loki]
```

`promtail-config.yml`:

```yaml
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
    relabel_configs:
      - source_labels: ["__meta_docker_container_name"]
        target_label: service
      - source_labels: ["__meta_docker_container_log_stream"]
        target_label: stream
```

Add Loki as a Grafana data source at `http://loki:3100`. Logs flow as: app stdout → Docker → Promtail → Loki → Grafana.

## Application setup (no SDK needed in containers)

For containerized deployments, the app just writes JSON to stdout — the agent (Promtail / Fluent Bit) handles shipping. Use the patterns from `cross-cutting/logging-structured.md` for log emission shape; nothing service-specific about Loki at the app layer.

For **non-container** deployments (VM, bare metal, serverless), use the `python-logging-loki` handler:

```python
import logging
import logging_loki

handler = logging_loki.LokiHandler(
    url="http://loki:3100/loki/api/v1/push",
    tags={"service": "rebooking", "env": "production"},
    version="1",
)
logger = logging.getLogger("rebooking")
logger.addHandler(handler)
```

For Node.js, `pino-loki` provides the same pattern as a pino transport.

## Schema (the discipline)

Every log line is one structured event. Adopting this once makes every query trivial; skipping it makes them all painful.

```json
{
  "timestamp":   "2026-05-22T10:15:00.123Z",
  "level":       "info",
  "service":     "rebooking",
  "env":         "production",
  "version":     "1.0.0",
  "trace_id":    "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id":     "00f067aa0ba902b7",
  "request_id":  "req-abc",
  "event_id":    "evt-abc",
  "msg":         "handler_succeeded",
  "duration_ms": 230
}
```

Standard fields, in order of usefulness:

- `timestamp` — ISO 8601 UTC.
- `level` — lowercase: `debug`, `info`, `warning`, `error`.
- `service`, `env`, `version` — set once via the logger config.
- `trace_id`, `span_id` — the same values OTel emits, so you can pivot between trace backend and logs.
- `request_id`, `tenant_id`, `event_id` — request-scoped identifiers.
- `msg` — a short snake_case `verb_subject` identifier (`handler_succeeded`, `event_dropped`), **not** an English sentence. The sentence ages badly; the identifier survives grep.
- Domain fields — explicit names (`duration_ms`, `event_action`), no nested unstructured maps.

## LogQL examples

```logql
# All error logs for one service
{service="rebooking", env="production", level="error"}

# Slow handlers
{service="rebooking"} | json | duration_ms > 1000

# One specific event id
{service="rebooking"} | json | event_id = "evt-abc"

# Error rate over time (chart in Grafana)
sum by (service) (rate({env="production", level="error"}[5m]))
```

Pair the data source with Grafana panels: error rate, latency-from-logs, request-id lookup, etc.

## Retention

Loki separates index from chunks; chunks ship to object storage (S3 / GCS / Azure Blob) cheaply.

| Tier | Retention | Cost driver |
|------|-----------|-------------|
| Hot (queryable) | 7–30 days | Index size + chunk cache |
| Cold (archive) | 1–7 years | Object storage |

Lifecycle rules on the bucket move chunks to colder tiers (Glacier, Coldline) automatically. Tighter retention on hot data is the main lever for query speed and cost.

## Sensitive data

NEVER log:

- Passwords, tokens, JWTs, API keys (filter at logger output).
- Full PII fields — log identifiers and a hash; resolve to values only at display time. See `cross-cutting/pii-gdpr.md` (PR-E, pending).
- Raw HTTP request bodies — they may carry uploaded content, secrets, PII.
- Stack traces with embedded secrets (rare but happens — error contexts sometimes echo input).

A safety net for the cases you missed — scrub known secret patterns at the logger:

```python
import logging
import re

SECRET_PATTERNS = [
    re.compile(r"sk-ant-[\w-]+"),                  # Anthropic
    re.compile(r"sk-[A-Za-z0-9]{40,}"),            # generic API key
    re.compile(r"eyJ[\w.-]+\.[\w.-]+\.[\w.-]+"),   # JWT
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access key id
]

class SecretRedactor(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pat in SECRET_PATTERNS:
            msg = pat.sub("<REDACTED>", msg)
        record.msg = msg
        record.args = ()
        return True

logging.getLogger().addFilter(SecretRedactor())
```

The filter is a backstop, not a primary control — keep secrets out of logs in the first place. But the cost of a backstop is near zero and one accidental `logger.info(settings)` will repay it for a year.

## Pitfalls

- **High-cardinality labels in Loki.** Loki indexes labels, not log content. Setting `request_id` as a label = one stream per request = index bloat and query slowness. Put high-cardinality values in the log line, not in labels.
- **Logging full request bodies.** PII + secrets in logs, surviving for the retention window.
- **Async fire-and-forget shipping with no buffer.** Logs lost during transient backend outage. Use a local buffer (Fluent Bit, Promtail) so the app doesn't block on the log pipe.
- **Different services using different field names for the same concept** (`req_id` vs `request_id` vs `requestId`). Pick one in `logging-structured.md` and enforce.
- **No retention policy** — log storage cost runaway; investigate-it-later means never investigate it.
- **English-sentence `msg` field** — breaks grep, ages badly. Use snake_case `verb_subject`.

## Where used in repo

- All recipes — structured logging is universal; centralized aggregation kicks in at Tier 2/3 deployments.

## Production considerations

- **Promtail / Fluent Bit DaemonSet** on Kubernetes — one log shipper per node tails container logs and forwards to Loki.
- **Multi-tenancy in Loki** via tenant headers (`X-Scope-OrgID`) — one Loki cluster, many isolated tenants.
- **Index size growth** — shard by service or tenant once a single index gets unwieldy.
- **Cold-storage lifecycle** — S3 Glacier / GCS Coldline for >30 day retention; tune per compliance requirements.
- **Network resilience** — a transient backend outage shouldn't drop logs; persistent file buffer on the shipper smooths it.

## See also

- `cross-cutting/logging-structured.md` — the emission patterns (structlog / pino, contextual binding).
- `opentelemetry.md` — share `trace_id` across logs and traces for cross-signal pivots.
- `prometheus-grafana.md` — the third leg; same Grafana surface for all three signals.
