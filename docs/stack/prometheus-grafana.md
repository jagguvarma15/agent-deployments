---
tags: [observability, metrics]
when_to_load: "recipe declares obs.grafana-stack"
---

# Stack pick: Prometheus + Grafana

> **Capability:** [`obs.grafana-stack`](../capabilities/obs/grafana-stack.md) (provisioning contract for `agent-scaffold up` — bundles Prometheus, Grafana, Tempo, and Loki via docker-compose).

**Choice:** Prometheus for metrics scraping; Grafana for dashboards + alerting
**Used for:** Service metrics (latency, throughput, error rates), business metrics (events processed by action, decisions per minute), SLO tracking

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Datadog / New Relic | Managed; expensive at scale; vendor lock-in |
| Prometheus + Grafana | Open source; CNCF standard; rich exporter / dashboard ecosystem |
| InfluxDB + Grafana | Push-based; great for IoT / time series; less natural fit for service metrics |
| StatsD + Graphite | Older protocol; still works but Prometheus is the modern default |
| Cloud-native (CloudWatch, Stackdriver) | Acceptable if single-cloud and Prometheus would be the only off-cloud thing you run |

For mise: Prometheus + Grafana self-hosted in dev / early prod; migrate to managed (Grafana Cloud, AWS Managed Prometheus, GCP Managed Prometheus) when ops bandwidth becomes the constraint.

## Local setup

```yaml
prometheus:
  image: prom/prometheus:latest
  command:
    - --config.file=/etc/prometheus/prometheus.yml
    - --storage.tsdb.retention.time=15d
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
    - prometheus_data:/prometheus
  ports: ["9090:9090"]

grafana:
  image: grafana/grafana:latest
  depends_on: [prometheus]
  ports: ["3001:3000"]
  volumes:
    - grafana_data:/var/lib/grafana
  environment:
    GF_SECURITY_ADMIN_PASSWORD: admin
```

`prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: rebooking
    static_configs:
      - targets: ["rebooking:8000"]
    metrics_path: /metrics
```

Grafana data source: add Prometheus at `http://prometheus:9090`.

## Python integration

```python
import time
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, Gauge, make_asgi_app

events_processed = Counter(
    "rebooker_events_processed_total",
    "Events processed, labeled by action",
    ["action"],                                  # bounded label set: ["rebooked", "deferred", "dropped", ...]
)

e2e_latency = Histogram(
    "rebooker_e2e_latency_seconds",
    "End-to-end latency from event arrival to outcome",
    buckets=[0.5, 1, 2, 5, 10, 30, 60, 120],
)

consumer_lag = Gauge(
    "rebooker_consumer_lag_seconds",
    "Seconds since last event was processed",
)

app = FastAPI()
app.mount("/metrics", make_asgi_app())

async def handle_event(event):
    start = time.monotonic()
    try:
        decision = await process(event)
        events_processed.labels(action=decision.action.value).inc()
    finally:
        e2e_latency.observe(time.monotonic() - start)
```

Background task to keep `consumer_lag` fresh:

```python
async def lag_refresher(app):
    while not app.state.shutting_down:
        consumer_lag.set(time.time() - app.state.last_processed_ts)
        await asyncio.sleep(5)
```

## TypeScript integration

```typescript
import { Counter, Histogram, Gauge, register } from "prom-client";
import { Hono } from "hono";

const eventsProcessed = new Counter({
  name: "rebooker_events_processed_total",
  help: "Events processed, labeled by action",
  labelNames: ["action"] as const,
});

const e2eLatency = new Histogram({
  name: "rebooker_e2e_latency_seconds",
  help: "End-to-end latency from event arrival to outcome",
  buckets: [0.5, 1, 2, 5, 10, 30, 60, 120],
});

const app = new Hono();
app.get("/metrics", async (c) =>
  c.text(await register.metrics(), 200, { "Content-Type": register.contentType }),
);
```

## Metric naming conventions

- Pattern: `<service>_<descriptor>_<unit>`. Example: `rebooker_events_processed_total`.
- **Counters end in `_total`.** Always.
- **Durations** end in `_seconds`. Always seconds — not milliseconds, not "ms". Convert at the source.
- **Sizes** end in `_bytes`.
- **Use labels for dimensions** (action, tenant_id, error_type, http_method). Keep cardinality bounded — under ~1000 unique label-value combinations per metric. `customer_id` as a label will OOM Prometheus.
- **Don't put units in label values.** `latency_seconds` not `latency{unit="seconds"}`.

## Alerting rules

Defined in Prometheus rule files or Grafana. Keep alert names imperative and the `for:` window short enough to detect, long enough not to flap.

```yaml
groups:
  - name: rebooker
    rules:
      - alert: HighConsumerLag
        expr: rebooker_consumer_lag_seconds > 60
        for: 2m
        labels: { severity: warning }
        annotations:
          summary: "Rebooker consumer lag > 60s"
          runbook: https://runbooks.internal/rebooker-high-lag

      - alert: HighDLQRate
        expr: rate(rebooker_events_dlq_total[5m]) > 0.1
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "Rebooker DLQ rate > 0.1/sec"

      - alert: SLOViolation_p95Latency
        expr: histogram_quantile(0.95, sum by (le) (rate(rebooker_e2e_latency_seconds_bucket[10m]))) > 60
        for: 10m
        labels: { severity: page }
        annotations:
          summary: "Rebooker p95 latency exceeds 60s SLO"
```

Pin a `runbook:` annotation on every page-level alert. Pager noise is cheap; missing runbooks at 3 AM is expensive.

## Grafana dashboards

Recommended panels for any HTTP service:

- Request rate (by endpoint, by status code)
- Error rate — `rate(http_requests_total{status=~"5.."}[5m])`
- Latency p50 / p95 / p99 — `histogram_quantile(...)` over the duration histogram
- Saturation — CPU, memory, file descriptors, queue depths

For event-driven (mise rebooking) add:

- Events processed (rate, by action)
- Consumer lag (gauge)
- Idempotency hits vs misses
- DLQ depth + DLQ insertion rate
- Tool call rate by tool
- E2E latency distribution

## SLO tracking via PromQL

Express SLOs as queries and alert on burn rate, not raw error rate. A multi-window burn-rate alert catches both fast and slow burns:

```promql
# Fast burn: alert when we'd burn 2% of the error budget in 1 hour
(
  sum(rate(rebooker_events_processed_total{status="failed"}[1h]))
  /
  sum(rate(rebooker_events_processed_total[1h]))
) > (14.4 * 0.01)   # 14.4× the 1% target error rate

# Slow burn: alert when we'd burn 10% of the error budget in 6 hours
(
  sum(rate(rebooker_events_processed_total{status="failed"}[6h]))
  /
  sum(rate(rebooker_events_processed_total[6h]))
) > (6 * 0.01)
```

Pair fast + slow windows so a sudden outage pages but a slow degradation isn't ignored.

## Pitfalls

- **High-cardinality labels** (e.g., `customer_id`, `request_id`, `url path`) — Prometheus stores a separate time series per label combination. Unbounded labels = OOM.
- **Scrape interval too short** — load on both the app and Prometheus; 15s is a good default.
- **No retention policy / no disk monitoring** — TSDB fills and the whole system stops scraping.
- **Dashboards without alerts** — pretty panels nobody watches. Every page-worthy condition needs an alert + a runbook.
- **Metrics inside hot allocation loops** — counters are cheap; histograms with many buckets less so.
- **Reusing metric names across services** — `errors_total` everywhere; aggregate queries become impossible. Prefix with the service name.
- **Forgetting to bound histogram buckets** — too-wide range = quantile estimation noise; too-narrow = missing the tail.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `/metrics` endpoint exposes `rebooker_*` metrics (events processed, e2e latency, consumer lag, DLQ rate).

## Production considerations

- **Retention.** Default is 15 days. For longer retention, use remote-write to Thanos / Cortex / Mimir, or use a managed offering.
- **HA.** Run Prometheus in pairs with identical scrape configs; deduplicate at query time (Thanos sidecar or Grafana data-source).
- **Grafana persistence.** Mount a volume for `/var/lib/grafana` so dashboards survive container restarts; back it up.
- **Recording rules.** Pre-compute expensive aggregations (e.g., per-tenant latency quantiles) on a schedule so dashboards query the cheap derived series.
- **Federation.** For multi-cluster setups, a top-level Prometheus scrapes aggregated metrics from per-cluster Prometheus instances.

## See also

- `opentelemetry.md` — the other half of the observability story (traces).
- `log-aggregation.md` — logs; correlate by `trace_id` across all three signals.
