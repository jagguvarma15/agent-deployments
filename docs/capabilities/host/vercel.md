---
id: host.vercel
kind: host
layer: frontend
provides: [edge_hosting, ci_deploy]
env_vars: [VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
provisioning_time: ~30s
cost_tier: fixed-monthly
est_tokens: 550
card:
  name: Vercel
  description: "Edge-hosted serverless deploy target with native Next.js + streaming-response support."
  capabilities_provided: [edge_hosting, ci_deploy, preview_envs]
  required_credentials: [VERCEL_TOKEN]
emit_files:
  - source: templates/vercel/vercel.json
    dest: vercel.json
  - source: templates/vercel/.vercelignore
    dest: .vercelignore
deploy_configs:
  - target: vercel
    cli_cmd: "vercel deploy --prod"
    dashboard_url: "https://vercel.com/dashboard"
    config_file: vercel.json
docs: |
  Vercel as the cloud host. Best fit with `frontend.nextjs-chat`. The
  emit_deploy_configs step writes `vercel.json` with env placeholders;
  `agent-scaffold deploy --target vercel` runs the Vercel CLI (dry-run by
  default).
tags: [host, serverless, frontend-first]
when_to_load: "recipe declares host.vercel"
---

# Capability: host.vercel

> Vendor docs: https://vercel.com/docs. CLI install: `npm i -g vercel`.

**Used for:** edge-hosted frontend deploys with native Next.js / Vercel AI SDK support.

## Local setup

**No docker fragment.** No local container. The `emit_deploy_configs` step writes `vercel.json` from the template with env-var placeholders filled where known.

## Deploy

```bash
# First-time setup (interactive, runs locally):
vercel link             # binds the project to a Vercel project

# Subsequent deploys via the scaffold:
agent-scaffold deploy --target vercel               # dry-run (prints command)
agent-scaffold deploy --target vercel --yes         # actually runs `vercel deploy --prod`
```

`agent-scaffold deploy` defaults to dry-run — it prints the command and dashboard URL, asks the user to confirm, then optionally executes.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `VERCEL_TOKEN` | *(secret)* | Personal API token from https://vercel.com/account/tokens — stored via keyring |
| `VERCEL_ORG_ID` | *(per project)* | Set by `vercel link`; lives in `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | *(per project)* | Set by `vercel link`; lives in `.vercel/project.json` |

## Client integration

Vercel is a deploy target — no runtime client wiring. The CLI is the integration surface:

```bash
# Set env vars in Vercel (production environment):
vercel env add ANTHROPIC_API_KEY production
vercel env add NEXT_PUBLIC_AGENT_URL production

# Deploy:
vercel deploy --prod

# Tail logs:
vercel logs <deployment-url>
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Project not found` on deploy | `vercel link` never ran | Run `vercel link` once interactively; commits `.vercel/project.json` |
| Deploy succeeds but 500 in prod | Env vars set locally but not in Vercel | `vercel env add VAR production`; redeploy |
| Build fails: "Module not found" | `node_modules` cached but lockfile updated | `vercel --force` to bust the build cache |
| Streaming responses hang | Vercel Edge timeout (default 10s) | Bump runtime config: `export const maxDuration = 60` in route handler; Pro plan required for >10s |

## See also

- [`capabilities/frontend/nextjs-chat.md`](../frontend/nextjs-chat.md) — natural pairing
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
