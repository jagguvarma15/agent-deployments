---
id: host.railway
kind: host
layer: frontend
provides: [container_hosting, managed_postgres, managed_redis]
env_vars: [RAILWAY_TOKEN, RAILWAY_PROJECT_ID]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
provisioning_time: ~60s
cost_tier: fixed-monthly
est_tokens: 500
card:
  name: Railway
  description: "Container-hosted backend with managed Postgres + Redis from one platform."
  capabilities_provided: [container_hosting, managed_postgres, managed_redis, ci_deploy]
  required_credentials: [RAILWAY_TOKEN]
emit_files:
  - source: templates/railway/railway.json
    dest: railway.json
  - source: templates/railway/.railwayignore
    dest: .railwayignore
deploy_configs:
  - target: railway
    cli_cmd: "railway up"
    dashboard_url: "https://railway.app/dashboard"
    config_file: railway.json
docs: |
  Railway as the cloud host. Pairs backend + managed Postgres/Redis in one
  platform. The emit_deploy_configs step writes `railway.json`;
  `agent-scaffold deploy --target railway` runs `railway up` (dry-run by
  default).
---

# Capability: host.railway

> Vendor docs: https://docs.railway.app. CLI install: `brew install railway` or `npm i -g @railway/cli`.

**Used for:** container-hosted backend + managed Postgres/Redis from one platform.

## Local setup

**No docker fragment.** No local container. The `emit_deploy_configs` step writes `railway.json` with build + deploy settings.

## Deploy

```bash
# First-time setup (interactive, runs locally):
railway login           # opens browser
railway link            # binds the project to a Railway project + environment

# Subsequent deploys:
agent-scaffold deploy --target railway              # dry-run
agent-scaffold deploy --target railway --yes        # runs `railway up`
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `RAILWAY_TOKEN` | *(secret)* | API token from `railway login` — stored via keyring |
| `RAILWAY_PROJECT_ID` | *(per project)* | Set by `railway link`; lives in `.railway/config.json` |

## Client integration

Railway is a deploy target — no runtime client wiring. The CLI surface:

```bash
# Provision managed Postgres:
railway add --plugin postgres

# Wire its connection string into your service:
railway variables --service backend --set DATABASE_URL='${{Postgres.DATABASE_URL}}'

# Deploy + tail:
railway up
railway logs --service backend
```

Railway's `${{ServiceName.VAR}}` syntax wires inter-service vars automatically — DATABASE_URL from the Postgres plugin lands in the backend service without manual paste.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Build failed: Dockerfile not found` | `railway.json` builder set to Dockerfile but file is missing | Ensure `Dockerfile` is committed at the path railway.json declares (default: project root) |
| Postgres plugin not visible to service | Plugin added but not wired | `railway variables --service backend --set DATABASE_URL='${{Postgres.DATABASE_URL}}'` |
| Cold-start latency for first request | Free tier sleeps idle services | Upgrade to a paid plan or use a health-check pinger |
| Logs cut off mid-line | Default log retention | `railway logs --service backend --json` exports the full structured log; archive externally |

## See also

- [`capabilities/relational/postgres.md`](../relational/postgres.md) — Railway-managed Postgres uses the same `DATABASE_URL` shape
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
