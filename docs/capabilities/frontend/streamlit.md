---
id: frontend.streamlit
kind: frontend
implements:
  port: frontend
  interface_version: "1.0"
layer: frontend
provides: [chat_ui]
env_vars: [AGENT_URL]
docker: null
probe: null
bootstrap_step: null
provisioning_time: ~5s
cost_tier: free
est_tokens: 500
card:
  name: Streamlit Chat UI
  description: "Single-file Streamlit chat template for Python-only stacks."
  capabilities_provided: [chat_ui, sse_streaming]
  required_credentials: []
emit_files:
  - source: templates/streamlit/**
    dest: frontend/
docs: |
  Streamlit chat template for Python-only stacks. Single-file UI with
  `st.chat_message` rendering and SSE streaming. Copied verbatim into
  frontend/ during generation.
tags: [frontend, python, prototype]
when_to_load: "recipe declares frontend.streamlit"
---

# Capability: frontend.streamlit

> Template tree: `templates/streamlit/` (sits next to this file). Vendor docs: https://docs.streamlit.io.

**Used for:** chat UI for Python agents in a single file with no Node toolchain.

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

## Client integration

The template ships with the agent-call wiring. The relevant glue:

```python
# frontend/streamlit_app.py (excerpt)
import streamlit as st
import httpx

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask the agent..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.chat_message("user").write(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        text = ""
        with httpx.stream("POST", f"{os.environ['AGENT_URL']}/agent",
                          json={"question": prompt}, timeout=120) as r:
            for chunk in r.iter_text():
                text += chunk
                placeholder.markdown(text)
    st.session_state.messages.append({"role": "assistant", "content": text})
```

## Cloud / production

- **Streamlit Community Cloud** — free for prototypes; deploy via GitHub integration.
- **Self-hosted** — `streamlit run` behind NGINX; CSRF/auth handled separately.

Pair with [`host.fly`](../host/fly.md) or [`host.railway`](../host/railway.md) for production deploys (Vercel doesn't host Python natively).

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused 8000` | Backend not yet running | Bring backend up first; verify `AGENT_URL` matches |
| Streaming chunks not appearing | httpx `iter_text` blocks per chunk | Confirm backend writes SSE-style (small chunks, flushed); not a single buffered write |
| Streamlit re-runs on every keystroke | Default behavior | Use `st.chat_input` (not `st.text_input`) — it batches submission on Enter |
| Session state lost on tab refresh | Streamlit session state is per-tab | Persist to `cache.redis` if cross-session continuity matters |

## See also

- `templates/streamlit/README.md` — template internals
- [`capabilities/host/fly.md`](../host/fly.md) — natural deploy target
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
