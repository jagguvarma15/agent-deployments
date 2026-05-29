"""Streamlit chat UI for the project's agent backend.

Calls ``POST $AGENT_URL/chat`` with the running message history and streams
the response into the assistant bubble. Falls back to a non-streaming POST
when the backend doesn't honor SSE.

Customization hooks:

- Per-recipe branding: edit ``st.title`` / ``st.caption`` below.
- Tool-call rendering: extend ``components/chat_message_with_tools.py``.
- Auth / cookies: add ``st.session_state["auth_token"]`` and forward it as
  a request header in :func:`_stream_chat` (and the fallback).
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from typing import Any

import httpx
import streamlit as st

from components.chat_message_with_tools import render_message

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8000").rstrip("/")
CHAT_ENDPOINT = f"{AGENT_URL}/chat"
REQUEST_TIMEOUT = 60.0


st.set_page_config(page_title="Agent", page_icon="🤖", layout="centered")
st.title("Agent")
st.caption(f"Backend: `{AGENT_URL}`")

if "messages" not in st.session_state:
    st.session_state["messages"] = []  # list[dict[str, Any]]

# Render the running history.
for msg in st.session_state["messages"]:
    render_message(msg)


def _stream_chat(messages: list[dict[str, Any]]) -> Iterator[str]:
    """Yield response chunks from the backend.

    Tries SSE first (``Accept: text/event-stream``); on a non-SSE response,
    falls back to reading the whole body and yielding it once.
    """
    payload = {"messages": messages}
    try:
        with httpx.stream(
            "POST",
            CHAT_ENDPOINT,
            json=payload,
            headers={"Accept": "text/event-stream"},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            response.raise_for_status()
            ctype = response.headers.get("content-type", "")
            if "event-stream" not in ctype and "text/plain" not in ctype:
                yield response.read().decode("utf-8", errors="replace")
                return
            for line in response.iter_lines():
                if not line:
                    continue
                # SSE: "data: <chunk>". AI SDK Data Stream: "0:\"chunk\"\n".
                if line.startswith("data:"):
                    chunk = line[len("data:") :].strip()
                    if chunk in ("[DONE]", ""):
                        continue
                    try:
                        parsed = json.loads(chunk)
                    except json.JSONDecodeError:
                        yield chunk
                        continue
                    if isinstance(parsed, str):
                        yield parsed
                    elif isinstance(parsed, dict) and "content" in parsed:
                        yield str(parsed["content"])
                    else:
                        yield json.dumps(parsed)
                elif line.startswith("0:"):
                    raw = line[2:]
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        yield raw
                else:
                    yield line
    except httpx.HTTPStatusError as exc:
        yield f"\n\n_Agent returned {exc.response.status_code}._"
    except httpx.HTTPError as exc:
        yield f"\n\n_Could not reach agent at {AGENT_URL}: {exc}_"


user_input = st.chat_input("Ask the agent…")
if user_input:
    user_msg = {"role": "user", "content": user_input}
    st.session_state["messages"].append(user_msg)
    render_message(user_msg)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        accumulated = ""
        for chunk in _stream_chat(st.session_state["messages"]):
            accumulated += chunk
            placeholder.markdown(accumulated)
        st.session_state["messages"].append({"role": "assistant", "content": accumulated})
