---
id: obs.grafana-stack
kind: obs
layer: observability
provides: [metrics, tracing, dashboards, alerting]
env_vars: [GRAFANA_URL, GRAFANA_ADMIN_PASSWORD, PROMETHEUS_URL, TEMPO_URL]
docker:
  service: grafana
  image: grafana/grafana:10.4.0
  ports: ["3002:3000"]
  volumes: ["grafana_data:/var/lib/grafana"]
  environment:
    GF_SECURITY_ADMIN_PASSWORD: "${GRAFANA_ADMIN_PASSWORD:-admin}"
    GF_AUTH_ANONYMOUS_ENABLED: "true"
    GF_AUTH_ANONYMOUS_ORG_ROLE: "Viewer"
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:3000/api/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 5
probe: grafana_health
bootstrap_step: bootstrap_observability
provisioning_time: ~30s
cost_tier: free
est_tokens: 950
card:
  name: Grafana stack (Grafana + Prometheus + Tempo)
  description: "Metrics + traces + dashboards for the full agent stack via OpenTelemetry."
  capabilities_provided: [metrics, distributed_tracing, dashboards, alerting]
  required_credentials: []
emit_files:
  - source: templates/grafana-stack/prometheus.yml
    dest: ops/prometheus/prometheus.yml
  - source: templates/grafana-stack/tempo.yaml
    dest: ops/tempo/tempo.yaml
  - source: templates/grafana-stack/dashboards/agent-overview.json
    dest: ops/grafana/dashboards/agent-overview.json
  - source: templates/grafana-stack/dashboards/infra.json
    dest: ops/grafana/dashboards/infra.json
docs: |
  Grafana + Prometheus + Tempo. Bootstrap step provisions datasources and
  uploads dashboards after the containers are healthy. Prometheus + Tempo
  run as additional compose services via emit_files.
tags: [observability, metrics, self-hosted]
when_to_load: "recipe declares obs.grafana-stack"
---

# Capability: obs.grafana-stack

> Deep reference: [`stack/prometheus-grafana.md`](../../stack/prometheus-grafana.md) and [`stack/opentelemetry.md`](../../stack/opentelemetry.md).

**Used for:** metrics (Prometheus), distributed traces (Tempo), dashboards + alerting (Grafana). The OpenTelemetry-native observability stack.

## Local setup

This capability emits **three** compose services (grafana + prometheus + tempo). Grafana lives in this capability's frontmatter `docker:` block; the other two land via `emit_files` (the resolver walks emit_files for adjacent compose snippets).

Web UIs after `docker compose up`:
- Grafana: `http://localhost:3002` (anonymous viewer; admin login via `admin` / `$GRAFANA_ADMIN_PASSWORD`)
- Prometheus: `http://localhost:9090`
- Tempo: `http://localhost:3200`

## Bootstrap (post docker_up)

`bootstrap_observability` waits for Grafana's `/api/health` to return OK, then:

1. POSTs the Prometheus + Tempo datasource definitions via `/api/datasources`.
2. POSTs each dashboard JSON from `ops/grafana/dashboards/*.json` via `/api/dashboards/db` (idempotent on `uid`).

```python
import urllib.request, json
req = urllib.request.Request(
    f"{os.environ['GRAFANA_URL']}/api/datasources",
    method="POST",
    headers={"Content-Type": "application/json",
             "Authorization": f"Basic {b64('admin:' + admin_password)}"},
    data=json.dumps({
        "name": "Prometheus", "type": "prometheus",
        "url": os.environ["PROMETHEUS_URL"], "access": "proxy", "isDefault": True
    }).encode(),
)
urllib.request.urlopen(req, timeout=5)
```

Stdlib only — no new client dep.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `GRAFANA_URL` | `http://localhost:3002` | Grafana base URL |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | **Must rotate** in production |
| `PROMETHEUS_URL` | `http://prometheus:9090` (compose) | Datasource URL Grafana uses |
| `TEMPO_URL` | `http://tempo:3200` (compose) | Tempo datasource URL |

## Client integration

**Python (OpenTelemetry):**

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(
    OTLPSpanExporter(endpoint=f"{os.environ['TEMPO_URL']}/v1/traces")
))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("agent.research"):
    response = await run_agent(question)
```

**TypeScript (@opentelemetry/sdk-node):**

```ts
import { NodeSDK } from "@opentelemetry/sdk-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";

const sdk = new NodeSDK({
  traceExporter: new OTLPTraceExporter({ url: `${process.env.TEMPO_URL}/v1/traces` }),
});
sdk.start();

import { trace } from "@opentelemetry/api";
const tracer = trace.getTracer("agent");
await tracer.startActiveSpan("agent.research", async (span) => {
  const response = await runAgent(question);
  span.end();
});
```

## Cloud / production

- **Grafana Cloud** — managed Grafana + Prometheus + Tempo. Set `GRAFANA_URL` to the stack URL and use a service-account token instead of admin password.
- **Self-hosted** — Grafana behind SSO (OAuth/SAML), persist `grafana_data` to a managed volume, separate Prometheus retention from Tempo retention.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| Datasources not added | Grafana healthcheck passed but admin auth failed | Verify `GRAFANA_ADMIN_PASSWORD` env matches what compose set; default is `admin` |
| Tempo shows no traces | OTLP exporter pointed at wrong endpoint | Use `${TEMPO_URL}/v1/traces` (HTTP path); gRPC port is different |
| Prometheus scrape targets down | `prometheus.yml` references compose service names | Confirm app and Prometheus are on the same compose network |
| Dashboard import returns 412 | Same `uid` already imported with different schema | Bump dashboard `version:` and re-import; or delete via API first |

## See also

- [`stack/prometheus-grafana.md`](../../stack/prometheus-grafana.md) — Prometheus + Grafana setup
- [`stack/opentelemetry.md`](../../stack/opentelemetry.md) — OTel instrumentation
- [`cross-cutting/observability.md`](../../cross-cutting/observability.md) — strategy
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
