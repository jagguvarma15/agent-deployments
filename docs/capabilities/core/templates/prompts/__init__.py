"""Owned, editable prompts.

The scaffold emits this package (the loader); you own the ``.md`` prompt files.
Edit them to change the agent's behavior — see README.md.
"""

from .loader import PromptNotFoundError, load_prompt

__all__ = ["PromptNotFoundError", "load_prompt"]
