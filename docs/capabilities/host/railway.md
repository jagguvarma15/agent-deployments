---
id: host.railway
kind: host
provides: [container_hosting, managed_postgres, managed_redis]
env_vars: [RAILWAY_TOKEN, RAILWAY_PROJECT_ID]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
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
  Railway as the cloud host. Strong fit when the project ships both a backend
  service and managed Postgres/Redis. The emit_deploy_configs step writes
  `railway.json`; `agent-scaffold deploy --target railway` runs `railway up`
  (dry-run by default).
---

# Capability: host.railway

> Vendor docs: https://docs.railway.app. CLI install: `brew install railway` or `npm i -g @railway/cli`.

**Used for:** container-hosted backend + managed Postgres/Redis from one platform.

## Why pick this

When the project has a Python or Node backend AND wants managed Postgres/Redis without provisioning them separately. Railway's UX for stacking services is one of the smoothest in the platform-as-a-service space. Trade-off: pricier per-resource than DIY Fly/Render at scale.

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

## When to swap it

- **→ `host.vercel`** if the project is frontend-only.
- **→ `host.fly`** for global edge with finer-grained pricing at scale.

## See also

- agent-scaffold Phase 4 brief — deploy verb internals
- `capabilities/relational/postgres.md` — Railway-managed Postgres uses the same `DATABASE_URL` shape
