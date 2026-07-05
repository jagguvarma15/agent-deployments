"""Load editable prompt files shipped alongside this package.

The agent's system prompt — and any other named prompt — lives in a plain-text
file next to this module. Edit ``agent/prompts/system.txt`` to change behavior;
no code change is needed.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent


class PromptNotFoundError(FileNotFoundError):
    """Raised when a named prompt file does not exist under ``agent/prompts/``."""


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Return the text of ``agent/prompts/<name>.txt``, stripped.

    ``name`` is a bare stem — no path separators, no extension. Cached because
    prompt files ship with the project and don't change at runtime.
    """
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise PromptNotFoundError(f"invalid prompt name: {name!r}")
    path = _PROMPTS_DIR / f"{name}.txt"
    if not path.is_file():
        raise PromptNotFoundError(f"no prompt file at {path}")
    return path.read_text(encoding="utf-8").strip()
