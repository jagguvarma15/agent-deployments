# I/O schema

Typed models for the agent's HTTP boundary — the canonical `/chat` contract:

- `ChatRequest` — the incoming body: `{"message": "...", "history": [...]}`
  (`message` non-empty; `history` may be empty).
- `ChatTurn` — one prior turn: `{"role": "user" | "agent", "text": "..."}`.
- `ChatResponse` — the outgoing body: `{"reply": "..."}`.

Import them in your handler so the boundary is validated and serialized against
a schema instead of hand-rolled dicts, and trim `history` to the context budget
before the model call (see `docs/cross-cutting/context-management.md`):

```python
from agent.context_window import context_input_max, to_model_messages, trim_history
from agent.io import ChatRequest, ChatResponse

@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    trimmed = trim_history(req.history, budget_tokens=context_input_max())
    reply = await run_agent(req.message, history=to_model_messages(trimmed))
    return ChatResponse(reply=reply)
```

A malformed body (missing/empty `message`) is rejected as a 422 by the framework
before your handler runs. Add fields — conversation id, metadata, a streaming
flag — as your agent grows; the frontend and backend share this one contract.
