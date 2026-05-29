---
id: host.vercel
kind: host
provides: [edge_hosting, ci_deploy]
env_vars: [VERCEL_TOKEN, VERCEL_ORG_ID, VERCEL_PROJECT_ID]
docker: null
probe: null
bootstrap_step: emit_deploy_configs
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
---

# Capability: host.vercel

> Vendor docs: https://vercel.com/docs. CLI install: `npm i -g vercel`.

**Used for:** edge-hosted frontend deploys with native Next.js / Vercel AI SDK support.

## Why pick this

The frictionless path for `frontend.nextjs-chat` projects. Native streaming-response support, edge functions, preview deploys per branch. Not the right host for Python backends — pair with `host.fly` or `host.railway` for those, and use Vercel for the UI only.

## Local setup

**No docker fragment.** No local container. The `emit_deploy_configs` step writes `vercel.json` from the template with env-var placeholders filled where known.

## Deploy

```bash
# First-time setup (interactive, runs locally on the user's machine):
vercel link             # binds the project to a Vercel project

# Subsequent deploys via the scaffold:
agent-scaffold deploy --target vercel               # dry-run (prints command)
agent-scaffold deploy --target vercel --yes         # actually runs `vercel deploy --prod`
```

`agent-scaffold deploy` (Phase 4) defaults to dry-run — it prints the command and dashboard URL, asks the user to confirm, then optionally executes. Cloud pushes never happen by surprise.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `VERCEL_TOKEN` | *(secret)* | Personal API token from https://vercel.com/account/tokens — stored via keyring |
| `VERCEL_ORG_ID` | *(per project)* | Set by `vercel link`; lives in `.vercel/project.json` |
| `VERCEL_PROJECT_ID` | *(per project)* | Set by `vercel link`; lives in `.vercel/project.json` |

The scaffold's secrets layer rotates `VERCEL_TOKEN` via `agent-scaffold secrets purge`.

## When to swap it

- **→ `host.railway`** for Postgres + agent backend in one platform.
- **→ `host.fly`** for global edge with Python or non-Next.js backends.

## See also

- `capabilities/frontend/nextjs-chat.md` — natural pairing
- agent-scaffold Phase 4 brief — deploy verb internals
