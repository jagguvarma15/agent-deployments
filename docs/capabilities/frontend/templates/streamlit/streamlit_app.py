"""Streamlit chat UI for the project's agent backend.

Calls ``POST $AGENT_URL/chat`` with the contract's ``{"message", "history"}``
body (prior turns oldest first, wire roles ``user``/``agent``) and streams
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
    falls back to reading the whole body and yielding it once. HTTP errors
    propagate to the caller, which renders them and marks the committed turn
    as a UI-local error so it is never re-sent as history.

    ``messages`` is the full session list including the just-appended user
    turn; the wire shape splits it into the /chat contract's ``message`` +
    ``history`` (session role ``assistant`` maps to wire role ``agent``).
    Error turns are filtered out, and the last 40 turns are a courtesy
    client cap — the backend trim is the authoritative bound.
    """
    if not messages:
        return
    *prior, latest = messages
    payload = {
        "message": str(latest.get("content", "")),
        "history": [
            {
                "role": "agent" if m.get("role") == "assistant" else "user",
                "text": str(m.get("content", "")),
            }
            for m in prior
            if not m.get("error")
        ][-40:],
    }
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


user_input = st.chat_input("Ask the agent…")
if user_input:
    user_msg = {"role": "user", "content": user_input}
    st.session_state["messages"].append(user_msg)
    render_message(user_msg)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        accumulated = ""
        error_text: str | None = None
        try:
            for chunk in _stream_chat(st.session_state["messages"]):
                accumulated += chunk
                placeholder.markdown(accumulated)
        except httpx.HTTPStatusError as exc:
            error_text = f"_Agent returned {exc.response.status_code}._"
        except httpx.HTTPError as exc:
            error_text = f"_Could not reach agent at {AGENT_URL}: {exc}_"
        if error_text is not None:
            # Render the failure, but mark the committed turn as UI-local:
            # error turns are filtered out of the history payload, so the
            # model is never told it previously answered with an error banner.
            placeholder.markdown(error_text)
            st.session_state["messages"].append(
                {"role": "assistant", "content": error_text, "error": True}
            )
        elif accumulated.strip():
            # Never commit an empty assistant turn (a stream that produced
            # nothing would otherwise cost budget on every later request).
            st.session_state["messages"].append({"role": "assistant", "content": accumulated})
