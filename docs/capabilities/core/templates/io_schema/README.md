# I/O schema

Typed models for the agent's HTTP boundary — the canonical `/chat` contract:

- `ChatRequest` — the incoming body: `{"message": "..."}` (non-empty).
- `ChatResponse` — the outgoing body: `{"reply": "..."}`.

Import them in your handler so the boundary is validated and serialized against
a schema instead of hand-rolled dicts:

```python
from agent.io import ChatRequest, ChatResponse

@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    reply = await run_agent(req.message)
    return ChatResponse(reply=reply)
```

A malformed body (missing/empty `message`) is rejected as a 422 by the framework
before your handler runs. Add fields — conversation id, metadata, a streaming
flag — as your agent grows; the frontend and backend share this one contract.
