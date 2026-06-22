"""Runtime environment setup for the dev sandbox.

A self-contained FastAPI router that lets the chat UI configure the agent's
environment at runtime when it wasn't pre-wired: the mandatory
``ANTHROPIC_API_KEY`` plus any optional services (LangSmith, a managed Redis, …).
So a freshly-cloned project can ``docker compose up``, open the chat, and fill
what's needed once. Mount it from your app and gate ``POST /chat`` with it (see
this capability's doc for the wiring).

The scaffold tells the form which vars to offer via the ``AGENT_SETUP_FIELDS``
env var (JSON ``[{"name", "required", "hint"}]``); absent, it defaults to just
``ANTHROPIC_API_KEY``. The chat UI calls ``GET /ready`` on load to decide whether
to show the configure panel.

Security model (single-tenant / **dev sandbox only**):

- The form is **CSRF-token-guarded** (constant-time compare).
- ``/setup`` + ``/ready`` are enabled by default; set ``AGENT_KEY_SETUP=0`` to
  disable ``/setup``. **Disable it on any public/production deployment.**
- Values are written to ``.env.local`` (mode 0600) and the process env. They are
  **never** echoed back to the browser, placed in a model prompt, or logged.
"""

from __future__ import annotations

import html
import json
import os
import secrets
import urllib.parse
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

KEY_NAME = "ANTHROPIC_API_KEY"
ENV_FILE = Path(os.environ.get("AGENT_ENV_FILE", ".env.local"))
_CSRF_TOKEN = secrets.token_urlsafe(16)
_SECRET_TOKENS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "_PAT")

router = APIRouter()


def _default_fields() -> list[dict[str, Any]]:
    return [
        {
            "name": KEY_NAME,
            "required": True,
            "hint": "console.anthropic.com → Settings → API Keys",
        }
    ]


def _fields() -> list[dict[str, Any]]:
    """The env vars to offer — from ``AGENT_SETUP_FIELDS``, else just the key."""
    raw = os.environ.get("AGENT_SETUP_FIELDS", "").strip()
    if not raw:
        return _default_fields()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _default_fields()
    out: list[dict[str, Any]] = []
    for item in data if isinstance(data, list) else []:
        name = item.get("name") if isinstance(item, dict) else None
        if isinstance(name, str) and name:
            out.append(
                {"name": name, "required": bool(item.get("required")), "hint": str(item.get("hint") or "")}
            )
    return out or _default_fields()


def _load_env_file() -> None:
    """Load ``KEY=VALUE`` lines from ``.env.local`` into the process env at import.

    So a value configured on a previous run (persisted to the host-mounted
    ``.env.local``) is available after a restart. Existing env values win.
    """
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        os.environ.setdefault(name.strip(), value.strip())


_load_env_file()


def _is_set(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def key_is_configured() -> bool:
    """Back-compat: True once the Anthropic key is available."""
    return _is_set(KEY_NAME)


def _missing_required() -> list[str]:
    return [f["name"] for f in _fields() if f["required"] and not _is_set(f["name"])]


def key_setup_required() -> JSONResponse | None:
    """Call at the top of ``POST /chat``.

    Returns a ``409`` pointing the chat UI at ``/setup`` when any **required** var
    is missing, else ``None`` (proceed with the model call).
    """
    missing = _missing_required()
    if not missing:
        return None
    return JSONResponse(
        status_code=409,
        content={"error": "missing: " + ", ".join(missing), "setup_url": "/setup"},
    )


def _setup_enabled() -> bool:
    """Dev sandbox: on by default; ``AGENT_KEY_SETUP=0`` disables it (prod)."""
    return os.environ.get("AGENT_KEY_SETUP", "1") != "0"


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness for the chat UI's proactive on-load check.

    ``{ready, missing_required, setup_url, fields:[{name, required, set, hint}]}``.
    Never returns any value — only whether each var is set.
    """
    fields = [
        {"name": f["name"], "required": f["required"], "hint": f["hint"], "set": _is_set(f["name"])}
        for f in _fields()
    ]
    missing = [f["name"] for f in fields if f["required"] and not f["set"]]
    return JSONResponse(
        {"ready": not missing, "missing_required": missing, "setup_url": "/setup", "fields": fields}
    )


_FORM_HEAD = """<!doctype html>
<html><head><meta charset="utf-8"><title>Configure your agent</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 640px;
         margin: 56px auto; padding: 0 16px; color: #222; }
  label { display: block; margin-top: 16px; font-weight: 600; }
  input { width: 100%; font-family: ui-monospace, monospace; font-size: 14px;
          padding: 8px; margin-top: 4px; box-sizing: border-box; }
  button { margin-top: 18px; padding: 8px 18px; font-size: 14px; cursor: pointer; }
  .hint { color: #666; font-size: 13px; font-weight: 400; margin-top: 2px; }
  .req { color: #b00; } .opt { color: #888; font-weight: 400; }
  code { background: #f3f3f3; padding: 1px 4px; border-radius: 3px; }
</style></head>
<body>
  <h2>Configure your agent</h2>
  <p class="hint">Fill what's needed and save. Values go straight into this
    agent's environment (and a mode-0600 <code>.env.local</code>) — never to the
    browser or the model's prompt. Optional fields can be left blank.</p>
  <form method="POST" action="/setup">
"""

_FORM_TAIL = """
    <button type="submit">Save &amp; start chatting</button>
  </form>
</body></html>
"""

_DONE_HTML = """<!doctype html>
<html><body style="font-family: system-ui, sans-serif; max-width: 560px;
margin: 80px auto; padding: 0 16px;">
<h2>Saved.</h2>
<p>You can close this tab and return to the chat — the agent is ready now.</p>
</body></html>
"""


def _is_secret(name: str) -> bool:
    upper = name.upper()
    return any(token in upper for token in _SECRET_TOKENS)


def _field_row(field: dict[str, Any]) -> str:
    name = field["name"]
    safe = html.escape(name)
    tag = '<span class="req">(required)</span>' if field["required"] else '<span class="opt">(optional)</span>'
    hint = f'<div class="hint">{html.escape(field["hint"])}</div>' if field["hint"] else ""
    input_type = "password" if _is_secret(name) else "text"
    placeholder = "sk-ant-..." if name == KEY_NAME else ""
    required_attr = " required" if field["required"] else ""
    return (
        f'<label for="{safe}">{safe} {tag}</label>{hint}'
        f'<input id="{safe}" type="{input_type}" name="{safe}" '
        f'placeholder="{placeholder}" autocomplete="off"{required_attr}>'
    )


def _render_form() -> str:
    rows = "\n".join(_field_row(f) for f in _fields())
    csrf = f'<input type="hidden" name="csrf" value="{_CSRF_TOKEN}">\n'
    return _FORM_HEAD + csrf + rows + _FORM_TAIL


@router.get("/setup", response_class=HTMLResponse)
def setup_form() -> HTMLResponse:
    if not _setup_enabled():
        return HTMLResponse("setup is disabled", status_code=404)
    return HTMLResponse(_render_form())


@router.post("/setup", response_class=HTMLResponse)
async def setup_submit(request: Request) -> HTMLResponse:
    if not _setup_enabled():
        return HTMLResponse("setup is disabled", status_code=404)
    raw = (await request.body()).decode("utf-8", errors="replace")
    posted = urllib.parse.parse_qs(raw)
    if not secrets.compare_digest((posted.get("csrf") or [""])[0], _CSRF_TOKEN):
        return HTMLResponse("rejected (bad CSRF token)", status_code=403)
    saved = 0
    for field in _fields():
        value = (posted.get(field["name"]) or [""])[0].strip()
        if value:
            os.environ[field["name"]] = value
            _persist_field(field["name"], value)
            saved += 1
    if saved == 0:
        return HTMLResponse("nothing to save — all fields were empty", status_code=400)
    return HTMLResponse(_DONE_HTML)


def _persist_field(name: str, value: str) -> None:
    """Write ``name=value`` to ``.env.local`` at mode 0600 (best-effort).

    Replaces any existing line for the var. A read-only or absent mount just means
    the value lives for this process only — the chat still works now. Never logs.
    """
    try:
        lines: list[str] = []
        if ENV_FILE.is_file():
            lines = [
                ln for ln in ENV_FILE.read_text().splitlines() if not ln.strip().startswith(f"{name}=")
            ]
        lines.append(f"{name}={value}")
        ENV_FILE.write_text("\n".join(lines) + "\n")
        ENV_FILE.chmod(0o600)
    except OSError:
        pass  # process env still has the value; persistence is best-effort
