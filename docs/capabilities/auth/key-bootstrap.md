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

# Runtime API-key bootstrap

Emits `agent_key_setup.py` (FastAPI, copied **verbatim** into the project root) so
a chat agent can capture its `ANTHROPIC_API_KEY` at runtime when the environment
doesn't already have one: the chat UI shows "Connect your API key", the user
pastes it into a CSRF-guarded `/setup` form served by the backend, and the agent
starts replying. The key is written to `.env.local` (mode 0600) and the process
env — it never goes to the browser or into a model prompt, and is never logged.

## Wiring (do this in the generated backend)

`agent_key_setup.py` is provided — **do not author or re-emit it**. Wire it in:

1. **Mount the router** on the FastAPI app:

   ```python
   from agent_key_setup import router as key_setup_router, key_setup_required
   app.include_router(key_setup_router)
   ```

2. **Gate `POST /chat`** so it returns the 409 when no key is configured (the
   frontend turns the returned `setup_url` into a "Connect your API key" button):

   ```python
   @app.post("/chat")
   async def chat(req: ChatRequest):
       gate = key_setup_required()
       if gate is not None:
           return gate            # 409 {"setup_url": "/setup"}
       ...                        # build the Anthropic client; return {"reply": ...}
   ```

3. Nothing else — `agent_key_setup` loads `.env.local` at import, so a key
   bootstrapped on a previous run is picked up automatically on the next restart.

## Notes

- **Dev sandbox only.** `/setup` is enabled by default; set `AGENT_KEY_SETUP=0`
  to disable it on any public/production deployment.
- Requires `fastapi` (already the backend's web framework) — no new packages.
- List `ANTHROPIC_API_KEY` and `AGENT_KEY_SETUP` in `.env.example` with comments.

No credentials are required up front — capturing one at runtime is the point.
