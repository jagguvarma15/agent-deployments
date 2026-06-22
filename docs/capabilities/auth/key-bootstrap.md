---
id: auth.key-bootstrap
kind: auth
layer: identity
provides: [runtime_key_capture]
env_vars: []
docker: null
serve_in_container: false
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
est_tokens: 450
emit_files:
  - source: templates/key-bootstrap/agent_key_setup.py
    dest: agent_key_setup.py
card:
  name: Runtime API-key bootstrap
  description: "Lets the chat UI capture the agent's Anthropic API key at runtime via a CSRF-guarded /setup form on the backend, when it wasn't pre-wired — so a freshly-cloned project can `docker compose up` and start chatting after pasting a key once. Dev sandbox only."
  capabilities_provided: [runtime_key_capture]
  required_credentials: []
tags: [auth, api-key, bootstrap, dev]
when_to_load: "a chat frontend is present and the agent needs a key to reply"
---

# Runtime environment bootstrap

Emits `agent_key_setup.py` (FastAPI, copied **verbatim** into the project root) so
a chat agent can configure its environment at runtime when it wasn't pre-wired —
the mandatory `ANTHROPIC_API_KEY` plus any optional services (LangSmith, a managed
Redis, …). The chat UI calls `GET /ready` on load and, if anything mandatory is
missing, shows a "Configure your agent" panel that opens a CSRF-guarded `/setup`
form. Values are written to `.env.local` (mode 0600) and the process env — never
sent to the browser, placed in a model prompt, or logged.

The router exposes `GET /ready`, `GET/POST /setup` automatically. The scaffold
passes the fields to offer via the `AGENT_SETUP_FIELDS` env var (you don't author
it); absent, the form defaults to just the Anthropic key.

## Wiring (do this in the generated backend)

`agent_key_setup.py` is provided — **do not author or re-emit it**. Wire it in:

1. **Mount the router** on the FastAPI app:

   ```python
   from agent_key_setup import (
       router as key_setup_router,
       key_setup_required,
       credential_error_response,
   )
   app.include_router(key_setup_router)
   ```

2. **Gate `POST /chat`** — return the 409 when a required var is missing, AND bounce
   back to setup when a key is set but *wrong* (an auth error from the SDK). The
   chat redirects to the secure `/setup` page on either, looping until it works:

   ```python
   @app.post("/chat")
   async def chat(req: ChatRequest):
       gate = key_setup_required()
       if gate is not None:
           return gate                       # 409 {"setup_url": "/setup"}
       try:
           ...                               # build the client; return {"reply": ...}
       except Exception as exc:              # noqa: BLE001
           redirect = credential_error_response(exc)
           if redirect is not None:
               return redirect               # 409 {"setup_url", "needs_setup": true}
           raise
   ```

3. Nothing else — `agent_key_setup` loads `.env.local` at import, so values
   configured on a previous run are picked up automatically on the next restart.
   The router also serves `GET /ready` (the chat's proactive check) and the
   `GET/POST /setup` form, which redirects back to the chat after saving.

## Notes

- **Dev sandbox only.** `/setup` is enabled by default; set `AGENT_KEY_SETUP=0`
  to disable it on any public/production deployment.
- Requires `fastapi` (already the backend's web framework) — no new packages.
- List `ANTHROPIC_API_KEY` and `AGENT_KEY_SETUP` in `.env.example` with comments.

No credentials are required up front — capturing one at runtime is the point.
