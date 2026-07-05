"""Schema-validated I/O for the agent boundary.

The scaffold emits these models; import them in your request handler instead of
passing raw dicts. See README.md.
"""

from .schemas import ChatRequest, ChatResponse

__all__ = ["ChatRequest", "ChatResponse"]
