"""Single-message renderer with optional tool-call expansion.

Treats any message with a ``tool_calls`` field as an assistant message that
made tool invocations; renders each call in a collapsible block under the
main bubble. Keeps the surface area small — generated projects extend this
function with domain-specific renderers (e.g. show a map for a location
tool, render a table for a SQL tool).
"""

from __future__ import annotations

from typing import Any

import streamlit as st


def render_message(msg: dict[str, Any]) -> None:
    role = msg.get("role", "assistant")
    with st.chat_message(role):
        content = msg.get("content", "")
        if content:
            st.markdown(content)

        tool_calls = msg.get("tool_calls") or []
        if tool_calls:
            with st.expander(f"Tool calls ({len(tool_calls)})", expanded=False):
                for call in tool_calls:
                    name = call.get("name") or call.get("function", {}).get("name", "tool")
                    args = call.get("args") or call.get("function", {}).get("arguments", {})
                    st.markdown(f"**{name}**")
                    st.code(_pretty(args), language="json")
                    result = call.get("result")
                    if result is not None:
                        st.markdown("_Result_")
                        st.code(_pretty(result), language="json")


def _pretty(value: Any) -> str:
    import json

    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)
