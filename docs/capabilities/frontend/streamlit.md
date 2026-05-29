---
id: frontend.streamlit
kind: frontend
provides: [chat_ui]
env_vars: [AGENT_URL]
docker: null
probe: null
bootstrap_step: null
emit_files:
  - source: templates/streamlit/**
    dest: frontend/
docs: |
  Streamlit chat template for Python-only stacks. Single-file UI with
  `st.chat_message` rendering and SSE streaming. Copied verbatim into
  frontend/ during generation; template tree lives next to this file under
  templates/streamlit/.
---

# Capability: frontend.streamlit

> Template tree: `templates/streamlit/` (sits next to this file). Vendor docs: https://docs.streamlit.io.

**Used for:** prototype chat UI for Python agents, when the goal is "I want a UI in one file with no Node."

## Why pick this

Single Python file, zero JavaScript, `streamlit run` and you're done. Trade-off: less polished than Next.js, weaker streaming UX, no production hosting story comparable to Vercel.

## Local setup

**No docker fragment.** Runs on the host (Python ≥ 3.11):

```bash
cd frontend
pip install -e .
streamlit run streamlit_app.py        # http://localhost:8501
```

## Template contract

`templates/streamlit/streamlit_app.py` ships with `st.chat_message` rendering and `httpx` SSE consumption. The generator wires the backend endpoint and optionally adds domain-specific message renderers in `components/`.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `AGENT_URL` | `http://localhost:8000` | Backend agent endpoint |

## Cloud / production

- **Streamlit Community Cloud** — free for prototypes; deploy via GitHub integration.
- **Self-hosted** — run via `streamlit run` behind an NGINX proxy; CSRF/auth need separate handling.

Not paired with `host.vercel` (Vercel doesn't host Python apps natively). Use `host.fly` or `host.railway` for Streamlit deployment.

## When to swap it

- **→ `frontend.nextjs-chat`** when the prototype works and you want a real production UI.

## See also

- `templates/streamlit/README.md` — template internals
- `capabilities/host/fly.md` — natural deploy target for Streamlit
