# I/O schema

Typed models for the agent's HTTP boundary — the canonical `/chat` contract:

- `ChatRequest` — the incoming body: `{"message": "...", "history": [...]}`
  (`message` non-empty; `history` may be empty).
- `ChatTurn` — one prior turn: `{"role": "user" | "agent", "text": "..."}`.
- `ChatResponse` — the outgoing body: `{"reply": "..."}`.

Import them in your handler so the boundary is validated and serialized against
a schema instead of hand-rolled dicts, and trim `history` to the context budget
before the model call. The trimming module is not emitted by this capability —
add `agent/context_window.py` from the reference implementation in
`docs/cross-cutting/context-management.md`, then:

```python
from agent.context_window import context_input_max, estimate_tokens, to_model_messages, trim_history
from agent.io import ChatRequest, ChatResponse

@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    budget = context_input_max() - estimate_tokens(SYSTEM_PROMPT) - estimate_tokens(req.message)
    trimmed = trim_history(req.history, budget_tokens=budget)
    reply = await run_agent(req.message, history=to_model_messages(trimmed))
    return ChatResponse(reply=reply)
```

Budget the history slice, not the whole window — the subtraction leaves room
for the system prompt and the latest message (add a further reserve when
retrieval or tool schemas enter the prompt).

A malformed body (missing/empty `message`) is rejected as a 422 by the framework
before your handler runs. Add fields — conversation id, metadata, a streaming
flag — as your agent grows; the frontend and backend share this one contract.
