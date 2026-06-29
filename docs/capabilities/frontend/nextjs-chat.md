---
id: frontend.nextjs-chat
kind: frontend
implements:
  port: frontend
  interface_version: "1.0"
layer: frontend
provides: [chat_ui, streaming_ui]
env_vars: [NEXT_PUBLIC_AGENT_URL]
docker: null
probe: null
bootstrap_step: null
provisioning_time: ~10s
cost_tier: free
est_tokens: 650
card:
  name: Next.js Chat UI
  description: "Next.js 14 (App Router) chat template wired for Vercel AI SDK streaming responses."
  capabilities_provided: [chat_ui, sse_streaming, tool_call_rendering]
  required_credentials: []
emit_files:
  - source: templates/nextjs-chat/**
    dest: frontend/
docs: |
  Next.js 14 (App Router) chat template wired to consume Vercel AI SDK
  responses from the backend's /api/agent endpoint. Copied verbatim into
  frontend/ during generation.
tags: [frontend, react, streaming]
when_to_load: "recipe declares frontend.nextjs-chat"
---

# Capability: frontend.nextjs-chat

> Template tree: `templates/nextjs-chat/` (sits next to this file). Vendor docs: https://sdk.vercel.ai/docs.

**Used for:** a runnable chat UI on `http://localhost:3000` that streams agent responses.

## Local setup

**No docker fragment.** The frontend runs on the host (Node ≥ 20). After generation:

```bash
cd frontend
pnpm install
pnpm dev          # http://localhost:3000
```

The scaffold's formatter runs `pnpm exec prettier --write frontend/` after copy when prettier is on PATH.

## Template contract

The scaffold copies the entire `templates/nextjs-chat/` subtree under `frontend/`. The generator must NOT re-emit any path matching this glob — the copier SKIPs with a warning if collision occurs.

LLM's responsibility for a frontend capability:
1. Wire backend endpoints the template expects (default: `POST /api/agent` returning a Vercel AI SDK stream).
2. Optionally specialize `frontend/app/page.tsx` (e.g. add domain-specific message bubbles).
3. Add per-recipe branding via `frontend/app/branding.ts` (generated file the template imports).

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `NEXT_PUBLIC_AGENT_URL` | `http://localhost:8000` | Backend agent endpoint the chat shell streams from. Public; safe to commit to `.env.example` |

## Client integration

The template ships with the agent-call wiring. The relevant glue:

```tsx
// frontend/app/page.tsx (excerpt from the shipped template)
"use client";
import { useChat } from "ai/react";

export default function Chat() {
  const { messages, input, handleInputChange, handleSubmit } = useChat({
    api: `${process.env.NEXT_PUBLIC_AGENT_URL}/api/agent`,
  });

  return (
    <main>
      {messages.map((m) => (
        <div key={m.id} className={m.role === "user" ? "u" : "a"}>
          {m.content}
        </div>
      ))}
      <form onSubmit={handleSubmit}>
        <input value={input} onChange={handleInputChange} />
      </form>
    </main>
  );
}
```

## Cloud / production

Pair with [`host.vercel`](../host/vercel.md). The emitted `vercel.json` (from `emit_deploy_configs`) sets `NEXT_PUBLIC_AGENT_URL` to the production agent URL.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Failed to fetch` on first message | Backend not yet listening on `NEXT_PUBLIC_AGENT_URL` | Bring up backend first (`docker compose up agent`); confirm port |
| CORS error in browser console | Backend doesn't allow the frontend origin | Add `http://localhost:3000` to the backend's CORS allowlist |
| Streaming text appears all at once | Backend buffers instead of streaming | Confirm backend writes `text/event-stream` headers; Vercel AI SDK reads SSE |
| `pnpm install` fails on Node 18 | Template requires Node ≥ 20 | Upgrade Node (`nvm install 20`); the README lists exact min |

## See also

- `templates/nextjs-chat/README.md` — template internals
- [`capabilities/host/vercel.md`](../host/vercel.md) — natural deploy target
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
