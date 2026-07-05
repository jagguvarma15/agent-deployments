---
id: core.io_schema
kind: core
implements:
  port: core
  interface_version: "1.0"
layer: agent
provides: [io_schema, request_validation]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: I/O schema
  description: "Pydantic request/response models for the canonical /chat contract — schema-validated I/O at the HTTP boundary. Part of the T0 chat substrate."
  capabilities_provided: [io_schema, request_validation]
  required_credentials: []
emit_files:
  - source: templates/io_schema/**
    dest: agent/io/
deploy_configs: []
docs: |
  Emits the agent/io/ package: Pydantic models for the canonical /chat contract
  (ChatRequest {message} -> ChatResponse {reply}). The generated backend imports
  these and validates request bodies / serializes responses against them instead
  of hand-rolling dicts, so the frontend<->backend boundary is typed and a
  malformed body is a 422 rather than a 500. Do NOT redefine the request/response
  shape inline — import it: `from agent.io import ChatRequest, ChatResponse`. The
  recipe/model can extend the models with extra fields (conversation id,
  metadata) as the agent grows.
tags: [core, io, validation]
when_to_load: "recipe tier is T0 or higher (the tier preset seeds core.io_schema)"
---

# Core: I/O schema

The boundary-validation substrate emitted at the **T0** tier. It ships typed
models for the agent's HTTP contract so requests are validated and responses are
serialized against a schema, not assembled as loose dicts.

## Emitted files

`emit_files` copies `templates/io_schema/**` into the project's `agent/io/`
package:

| File | Role |
|---|---|
| `schemas.py` | `ChatRequest` / `ChatResponse` — the `/chat` request and reply models (Pydantic). |
| `__init__.py` | Re-exports the models (`from agent.io import ChatRequest, ChatResponse`). |
| `README.md` | How to wire the models into the request handler and extend them. |

The copier never overwrites a file the model emitted at the same path, so a
recipe can specialize the schema while inheriting the package.

## Wiring

The `/chat` handler takes a `ChatRequest` and returns a `ChatResponse`, so the
canonical `{"message"}` → `{"reply"}` contract is enforced by the framework:

```python
from agent.io import ChatRequest, ChatResponse

@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await run_agent(req.message)
    return ChatResponse(reply=reply)
```

## See also

- `frontend.minimal-chat` posts `{"message"}` and renders `{"reply"}` — the other
  half of this contract.
