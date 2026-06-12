---
tags: [observability, tracing, otel]
when_to_load: "recipe needs OTel instrumentation"
---

# Stack pick: OpenTelemetry

**Choice:** OpenTelemetry SDK — `opentelemetry-sdk` (Python), `@opentelemetry/sdk-node` (TypeScript)
**Backend:** OTel Collector → Jaeger / Tempo / Datadog / Honeycomb (your choice)
**Used for:** Distributed tracing across services, beyond LLM-specific Langfuse spans

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Vendor SDK (Datadog APM, New Relic) | Lock-in; OTel + Collector lets you swap backends without app code changes |
| Langfuse only | Langfuse is LLM-shaped; it doesn't trace Redis / Postgres / outbound HTTP spans |
| Jaeger SDK direct | Deprecated; OTel is the CNCF standard and the migration target |
| No tracing | Acceptable for prototypes; not for anything multi-service in production |

For mise: OTel SDK in the app + an OTel Collector + Langfuse alongside for LLM-specific spans. Correlate via shared `trace_id`.

## Three signals

OTel unifies **traces**, **metrics**, and **logs** under one SDK + collector. Most teams adopt traces first, then logs, then metrics — though metrics are often already covered by Prometheus (see `prometheus-grafana.md`).

- **Traces** — span tree describing what happened in a request
- **Metrics** — numeric measurements over time
- **Logs** — structured events (also see `log-aggregation.md`)

## Local setup

OTel Collector + Jaeger via docker-compose:

```yaml
otel-collector:
  image: otel/opentelemetry-collector-contrib:latest
  command: ["--config=/etc/otel-collector-config.yaml"]
  volumes:
    - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
  ports:
    - "4317:4317"   # OTLP gRPC
    - "4318:4318"   # OTLP HTTP

jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"   # UI
    - "4317"          # OTLP intake from collector
```

`otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: 0.0.0.0:4317 }
      http: { endpoint: 0.0.0.0:4318 }

processors:
  batch: {}                                 # smooths bursts
  memory_limiter:                            # back-pressure on memory pressure
    check_interval: 1s
    limit_percentage: 80
    spike_limit_percentage: 25

exporters:
  otlp/jaeger:
    endpoint: jaeger:4317
    tls: { insecure: true }

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/jaeger]
```

Browse traces at `http://localhost:16686`.

## Python integration

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

resource = Resource.create({
    "service.name":    "rebooking",
    "service.version": "1.0.0",
    "deployment.environment": settings.env,
})
provider = TracerProvider(resource=resource)
provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True))
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)

# Auto-instrument popular libs (one line each, before the app starts handling requests)
from opentelemetry.instrumentation.fastapi    import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx      import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis      import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

FastAPIInstrumentor.instrument_app(app)
HTTPXClientInstrumentor().instrument()
RedisInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument(engine=engine)

# Manual span for an event handler
async def handle_event(event: Event) -> None:
    with tracer.start_as_current_span(
        "handle_event",
        attributes={"event.id": event.event_id, "event.type": event.type},
    ):
        await enrich(event)
        await decide(event)
        await act(event)
```

Shut the SDK down cleanly on exit so the last batch flushes:

```python
@asynccontextmanager
async def lifespan(app):
    yield
    provider.shutdown()
```

## TypeScript integration

```typescript
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-grpc";
import { getNodeAutoInstrumentations } from "@opentelemetry/auto-instrumentations-node";
import { resourceFromAttributes } from "@opentelemetry/resources";

const sdk = new NodeSDK({
  resource: resourceFromAttributes({
    "service.name": "rebooking",
    "service.version": "1.0.0",
    "deployment.environment": process.env.APP_ENV ?? "development",
  }),
  traceExporter: new OTLPTraceExporter({ url: "http://otel-collector:4317" }),
  instrumentations: [getNodeAutoInstrumentations()],
});

sdk.start();
process.on("SIGTERM", () => sdk.shutdown());
```

## Trace context propagation across event queues

OTel auto-instruments HTTP and gRPC, but event queues (Redis Streams, Kafka, SQS) are application-level — you have to propagate the trace context yourself. Inject the W3C `traceparent` into the event payload and extract it on the consumer side:

```python
import json
from opentelemetry.propagate import inject, extract

# Producer
async def publish_event(stream: str, event: Event) -> None:
    carrier: dict[str, str] = {}
    inject(carrier)              # writes "traceparent" into carrier
    await redis.xadd(stream, {
        **event.model_dump(),
        "_otel_carrier": json.dumps(carrier),
    })

# Consumer
async def handle_message(fields: dict) -> None:
    carrier = json.loads(fields.get("_otel_carrier", "{}"))
    parent_ctx = extract(carrier)
    with tracer.start_as_current_span("handle_event", context=parent_ctx):
        await process(fields)
```

Without this, every queue boundary breaks the trace into two unrelated trees — you lose the ability to see end-to-end latency.

## Sampling

Production deployments sample to control cost (every span is bytes in the collector and bytes on the backend).

| Sampler | Use case |
|---------|----------|
| `AlwaysOn` / `AlwaysOff` | Dev only |
| `TraceIdRatioBased` | Sample N% of traces (head-based) |
| `ParentBased` | Respect upstream's decision — keeps traces internally consistent |
| Tail-based (collector-side) | Sample based on outcome: always keep errors, sample successes |

A common production shape:

- **Head**: `ParentBased(root=TraceIdRatioBased(0.1))` — keep 10% of root spans, propagate the decision downstream.
- **Tail (collector)**: keep 100% of traces containing an error or a span over a latency threshold.

```yaml
# Collector tail-sampling processor
processors:
  tail_sampling:
    decision_wait: 30s
    policies:
      - { name: errors,   type: status_code, status_code: { status_codes: [ERROR] } }
      - { name: slow,     type: latency,     latency: { threshold_ms: 1000 } }
      - { name: default,  type: probabilistic, probabilistic: { sampling_percentage: 10 } }
```

## Integration with Langfuse

Use OTel for service spans (HTTP / DB / Redis / queue) and Langfuse for LLM-specific spans (prompt, tokens, model, cost). Pin both to the same `trace_id` so you can pivot between backends:

- Pass the `trace_id` from the current OTel span as the Langfuse `trace_id`.
- Langfuse 2.x also supports OTLP ingestion directly if you want a single backend for both.

## Config knobs that matter

| Env var | Default | Effect |
|---------|---------|--------|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | Collector endpoint URL |
| `OTEL_SERVICE_NAME` | — | Service identifier in traces |
| `OTEL_RESOURCE_ATTRIBUTES` | — | Extra resource-level key=value pairs |
| `OTEL_TRACES_SAMPLER` | `parentbased_always_on` | Sampling strategy |
| `OTEL_TRACES_SAMPLER_ARG` | — | Ratio for ratio-based samplers (0.0–1.0) |
| `OTEL_PROPAGATORS` | `tracecontext,baggage` | Propagation formats |

## Pitfalls

- **No propagation across queues** — broken traces at every async boundary.
- **100% sampling in prod** — exporter overhead + storage cost; head-sample, then tail-sample for keep-on-error.
- **Forgetting to `shutdown()` on exit** — last batch lost.
- **PII in span attributes** — leaks into the trace backend with the same retention as any other span.
- **Mixing OTel and a vendor SDK in the same process** — duplicate spans, two trace trees, confusion.
- **Resource attribute drift** — every service uses a different `service.name` shape (e.g. `rebooker` vs `rebooking-svc`). Standardize once.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — propagates `trace_id` from the cancellation event payload through the orchestrator and tool calls.

## Production considerations

- **Collector HA** — run 3+ Collector replicas behind a service mesh or LB. The Collector is on the critical path for any in-app span emission.
- **Buffer for bursts** — `batch` + `memory_limiter` processors smooth spikes and prevent the Collector OOM-ing under load.
- **Backend choice** — Tempo (Grafana stack) + Loki (logs) + Prometheus (metrics) is a coherent self-hosted bundle. Datadog / Honeycomb / Lightstep are managed alternatives.
- **Cost shape** — most observability backends charge per ingested byte; sampling is the main cost lever.

## See also

- `tracing-langfuse.md` — LLM-specific tracing; correlates by `trace_id`.
- `prometheus-grafana.md` — metrics (the other OTel signal most teams adopt separately).
- `log-aggregation.md` — log shipping; ties to traces via `trace_id`.
