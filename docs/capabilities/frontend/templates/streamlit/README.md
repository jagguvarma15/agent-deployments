# streamlit template

The agent-scaffold capability `frontend.streamlit` copies this directory verbatim into the generated project under `frontend/`. The result is a single-file Streamlit chat UI that talks to the project's agent service.

## Run locally

```bash
cd frontend
pip install -e .
streamlit run streamlit_app.py        # http://localhost:8501
```

Override the backend URL via env:

```
AGENT_URL=http://localhost:8000
```

## Required backend contract

The chat UI calls `POST ${AGENT_URL}/chat` with `{"messages": [{"role", "content"}, ...]}`. Two response shapes are accepted:

1. **SSE / streaming** — `text/event-stream` or `text/plain` with chunks framed as `data: <chunk>` (SSE) or `0:<json-string>` (AI SDK Data Stream). The UI renders chunks as they arrive.
2. **Non-streaming** — any other content-type. The UI reads the full body and renders it once.

Tool-call messages get an inline expander; see `components/chat_message_with_tools.py` for the rendering hook.

## Customizing per recipe

Generated projects typically extend the template in two places:

1. **`streamlit_app.py`** — change the `st.title` / `st.caption`, add sidebar controls (model picker, eval feedback, etc.).
2. **`components/chat_message_with_tools.py`** — render domain-specific tool calls (a map for a location lookup, a table for a SQL query, etc.).

## Smoke-tested with

- `pip install -e .` resolves dependencies cleanly against Python 3.11+
- `streamlit run streamlit_app.py --server.headless true` starts without import errors; the chat input renders. With no backend running you'll see `_Could not reach agent at http://localhost:8000_` in the assistant bubble.

## Why these choices

- **Streamlit ≥ 1.30**: required for the `st.chat_message` / `st.chat_input` API.
- **httpx for SSE**: stdlib `urllib` doesn't stream; `requests` doesn't either. `httpx.stream()` is the lightest dep that handles both happy paths.
- **No async**: Streamlit's runtime is single-threaded per session; sync httpx keeps the code straightforward.
