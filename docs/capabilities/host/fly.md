---
id: host.fly
kind: host
provides: [container_hosting, global_edge]
env_vars: [FLY_API_TOKEN, FLY_APP_NAME]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
emit_files:
  - source: templates/fly/fly.toml
    dest: fly.toml
  - source: templates/fly/.dockerignore
    dest: .dockerignore
deploy_configs:
  - target: fly
    cli_cmd: "fly deploy"
    dashboard_url: "https://fly.io/dashboard"
    config_file: fly.toml
docs: |
  Fly.io as the cloud host. Strong fit for global low-latency backends in any
  language. The emit_deploy_configs step writes `fly.toml`; `agent-scaffold
  deploy --target fly` runs `fly deploy` (dry-run by default). First-time
  deploys need an interactive `fly launch --no-deploy` to register the app.
---

# Capability: host.fly

> Vendor docs: https://fly.io/docs. CLI install: `curl -L https://fly.io/install.sh | sh`.

**Used for:** container-hosted backend with global region rollout. Language-agnostic.

## Why pick this

When the backend should run close to users across multiple regions, and Vercel's serverless model is the wrong shape (long-lived agent processes, websockets, GPU). Fly's Machines API gives per-region control with sane defaults. Trade-off: less polished managed-DB story than Railway (Fly Postgres exists but is more DIY).

## Local setup

**No docker fragment.** No local container — Fly builds from the project's `Dockerfile`. The `emit_deploy_configs` step writes `fly.toml` with build + deploy settings.

## Deploy

```bash
# First-time setup (interactive):
fly auth login
fly launch --no-deploy        # registers the app; writes app name into fly.toml

# Subsequent deploys:
agent-scaffold deploy --target fly                  # dry-run
agent-scaffold deploy --target fly --yes            # runs `fly deploy`
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `FLY_API_TOKEN` | *(secret)* | Personal access token from `fly auth token` — stored via keyring |
| `FLY_APP_NAME` | *(per project)* | Set by `fly launch`; lives in `fly.toml` |

## Secrets on Fly

Per-environment secrets are pushed via `fly secrets set KEY=value`. The scaffold doesn't automate this in v1 — it prints the list of secrets the user needs to set, derived from the resolved capabilities' env_vars (minus the ones safe to commit like `NEXT_PUBLIC_*`).

## When to swap it

- **→ `host.railway`** if managed Postgres / Redis from the same platform is more important than per-region edge.
- **→ `host.vercel`** for Next.js + serverless workloads only.

## See also

- agent-scaffold Phase 4 brief — deploy verb internals
- `capabilities/frontend/streamlit.md` — Streamlit on Fly is the canonical Python-frontend deploy
