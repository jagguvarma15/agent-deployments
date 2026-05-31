---
id: obs.grafana-stack
kind: obs
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
  Grafana + Prometheus + Tempo. Bootstrap step provisions the datasources and
  uploads dashboards after the containers are healthy. Prometheus + Tempo run
  as additional compose services — the emit_files plumbs their configs.
---

# Capability: obs.grafana-stack

> Deep reference: [`stack/prometheus-grafana.md`](../../stack/prometheus-grafana.md) and [`stack/opentelemetry.md`](../../stack/opentelemetry.md).

**Used for:** metrics (Prometheus), distributed traces (Tempo), dashboards + alerting (Grafana). The full OTel-style observability stack.

## Why pick this

When the observability target spans more than LLM calls — HTTP latency, queue depth, DB connection pool saturation, custom counters. Plays well with apps that already emit OTel telemetry. Higher ops cost than `obs.langsmith`; the dashboards make the trade worthwhile once the system has more than three moving parts.

## Local setup

This capability emits **three** compose services (grafana + prometheus + tempo) via fragments merged into `docker-compose.yml`. Only `grafana` is in this capability's frontmatter `docker:` block; the other two land via `emit_files` (Phase 1b's resolver also walks emit_files for adjacent compose snippets — see capability authoring docs).

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

## Cloud / production

- **Grafana Cloud** — managed Grafana + Prometheus + Tempo. Set `GRAFANA_URL` to the stack URL and use a service account token instead of admin password.
- **Self-hosted** — put Grafana behind SSO (OAuth/SAML), persist `grafana_data` to a managed volume, separate Prometheus retention from Tempo retention.

## When to swap it

- **→ `obs.langsmith`** or **`obs.langfuse`** for LLM-only observability.

## See also

- `stack/prometheus-grafana.md` — Prometheus + Grafana setup
- `stack/opentelemetry.md` — OTel instrumentation for the agent
- `cross-cutting/observability.md` — strategy doc
