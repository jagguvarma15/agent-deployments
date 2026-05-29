---
id: frontend.nextjs-chat
kind: frontend
provides: [chat_ui, streaming_ui]
env_vars: [NEXT_PUBLIC_AGENT_URL]
docker: null
probe: null
bootstrap_step: null
emit_files:
  - source: templates/nextjs-chat/**
    dest: frontend/
docs: |
  Next.js 14 (App Router) chat template wired to consume Vercel AI SDK
  responses from the backend's /api/agent endpoint. Copied verbatim into
  frontend/ during generation; templates live in a sibling PR (Phase 3a).
---

# Capability: frontend.nextjs-chat

> Template tree: `templates/nextjs-chat/` (shipped by Phase 3a). Vendor docs: https://sdk.vercel.ai/docs.

**Used for:** a runnable chat UI on `http://localhost:3000` that streams agent responses.

## Why pick this

The web-standard demo UI for agent projects. Vercel AI SDK gives you streaming + tool-call rendering with `useChat`. Tailwind for styling, App Router for routing, minimal dependencies. Pairs natively with `host.vercel` for one-command cloud deploy.

## Local setup

**No docker fragment.** The frontend runs on the host (Node ≥ 20). After generation:

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
```

The scaffold's dual-language formatter (Phase 3b) runs `pnpm exec prettier --write frontend/` after copy.

## Template contract

The scaffold copies the entire `templates/nextjs-chat/` subtree (Phase 3a) under `frontend/`. The LLM (taught by Phase 5 prompt updates) must NOT re-emit any path matching this glob — the copier SKIPs with a warning if collision occurs.

The LLM's responsibility for a frontend capability:
1. Wire backend endpoints the template expects (default: `POST /api/agent` returning a Vercel AI SDK stream).
2. Optionally specialize `frontend/app/page.tsx` by writing a thin override that imports from the shipped template (e.g. add domain-specific message bubbles).
3. Add per-recipe branding via `frontend/app/branding.ts` (a generated file the template imports).

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `NEXT_PUBLIC_AGENT_URL` | `http://localhost:8000` | Backend agent endpoint the chat shell streams from. Public; safe to commit to `.env.example` |

## Cloud / production

Pair with `host.vercel`. The emitted `vercel.json` (from `emit_deploy_configs` step) sets `NEXT_PUBLIC_AGENT_URL` to the production agent URL.

## When to swap it

- **→ `frontend.streamlit`** for Python-only stacks or rapid prototyping without Node.
- **→ assistant-ui** (future capability) for richer multimodal tool-call UI.

## See also

- `templates/nextjs-chat/README.md` (Phase 3a) — template internals
- `capabilities/host/vercel.md` — natural deploy target
