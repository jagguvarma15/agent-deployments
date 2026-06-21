---
id: frontend.minimal-chat
kind: frontend
layer: frontend
provides: [chat_ui]
env_vars: [VITE_AGENT_URL]
docker: null
serve_in_container: true
probe: null
bootstrap_step: null
provisioning_time: ~15s
cost_tier: free
est_tokens: 600
card:
  name: Minimal Chat UI (Vite + React)
  description: "A tiny Vite + React + TypeScript chat that POSTs to the backend and renders the reply. Built once and served from nginx as a container — the default frontend for every agent."
  capabilities_provided: [chat_ui]
  required_credentials: []
emit_files:
  - source: templates/minimal-chat/**
    dest: frontend/
---

# Minimal Chat UI (Vite + React + TypeScript)

The **default frontend** the scaffold ships with every generated agent so the
docker sandbox always has a **frontend + backend** to eyeball. It is added
automatically when a recipe declares no other `frontend.*` capability.

- **Containerized.** `serve_in_container: true` + a multi-stage `Dockerfile`
  (Node build → nginx serve on **:3000**). The scaffold's `normalize_frontend_service`
  pass adds a `frontend` compose service (`build: ./frontend`, port 3000,
  `depends_on` the backend) so one `docker compose up` brings up both containers.
- **Backend wiring.** The UI reads `VITE_AGENT_URL` (default `http://localhost:8000`
  — the host-mapped backend port the browser reaches). The scaffold wires this
  env var to the backend automatically.
- **Endpoint contract.** The UI sends `POST {VITE_AGENT_URL}/chat` with a JSON body
  `{"message": "<text>"}` and renders the response — JSON `{"reply": "..."}` (or
  `{"answer": "..."}`), or plain text. **The agent's backend should expose a
  `POST /chat` route** returning the reply. Recipes whose backend uses a different
  route can either add a thin `/chat` alias or override `VITE_AGENT_URL`'s path.
  The full, canonical contract lives in [`docs/reference/chat-contract.md`](../../reference/chat-contract.md).
- **Title.** The scaffold passes a `VITE_AGENT_TITLE` build arg (from the
  "describe your agent" step); the UI shows it as the page + header title,
  defaulting to "Agent Chat".

No credentials required.
