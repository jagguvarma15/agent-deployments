---
id: host.fly
kind: host
layer: frontend
provides: [container_hosting, global_edge]
env_vars: [FLY_API_TOKEN, FLY_APP_NAME]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
provisioning_time: ~60s
cost_tier: fixed-monthly
est_tokens: 500
card:
  name: Fly.io
  description: "Container-hosted backend with per-region rollout and Fly Machines API for fine-grained scaling."
  capabilities_provided: [container_hosting, global_edge, multi_region, ci_deploy]
  required_credentials: [FLY_API_TOKEN]
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
  Fly.io as the cloud host. Container-hosted backend with global region
  rollout. The emit_deploy_configs step writes `fly.toml`;
  `agent-scaffold deploy --target fly` runs `fly deploy` (dry-run by default).
  First-time deploys need an interactive `fly launch --no-deploy`.
tags: [host, paas, docker]
when_to_load: "recipe declares host.fly"
---

# Capability: host.fly

> Vendor docs: https://fly.io/docs. CLI install: `curl -L https://fly.io/install.sh | sh`.

**Used for:** container-hosted backend with global region rollout. Language-agnostic.

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

Per-environment secrets are pushed via `fly secrets set KEY=value`. The scaffold prints the list of secrets to set, derived from resolved capabilities' env_vars (minus `NEXT_PUBLIC_*` and other safe-to-commit vars).

## Client integration

Fly is a deploy target — no runtime client wiring. The CLI surface:

```bash
# Set secrets (persisted in Fly's secret store):
fly secrets set ANTHROPIC_API_KEY=sk-ant-... LANGFUSE_SECRET_KEY=...

# Deploy + scale per region:
fly deploy
fly scale count 2 --region ord
fly scale count 2 --region fra

# Tail logs:
fly logs
```

The `Dockerfile` is the contract — Fly builds, ships, and runs it. Multi-region rollout is one flag away.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `App name "X" is taken` | Fly apps are globally unique | Pick a different name in `fly launch --no-deploy` |
| Deploy succeeds but 502 | Health check failing | Ensure `[checks]` in `fly.toml` matches the app's `/health` endpoint |
| `fly secrets set` requires restart | Fly restarts the VM on secret change | Expected; `fly secrets set --stage` to batch without restart, then `fly deploy` |
| Build OOM | Default builder is small | `fly deploy --build-only --remote-only` uses Fly's remote builder with more RAM |

## See also

- [`capabilities/frontend/streamlit.md`](../frontend/streamlit.md) — Streamlit on Fly
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
