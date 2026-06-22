"""Runtime API-key bootstrap for the dev sandbox.

A self-contained FastAPI router that lets the chat UI capture the agent's
``ANTHROPIC_API_KEY`` at runtime when it wasn't pre-wired into the environment —
so a freshly-cloned project can ``docker compose up`` and start chatting after
pasting a key once. Mount it from your app and gate ``POST /chat`` with it
(see this capability's doc for the three lines of wiring).

Security model (single-tenant / **dev sandbox only**):

- The form is **CSRF-token-guarded** (constant-time compare) so a malicious page
  can't drive the listener.
- ``/setup`` is enabled by default for the sandbox; set ``AGENT_KEY_SETUP=0`` to
  disable it. **Disable it on any public/production deployment** — otherwise a
  missing key lets anyone set one.
- The key is written to ``.env.local`` (mode 0600) and the process env. It is
  **never** echoed back to the browser, placed in a model prompt, or logged.
"""

from __future__ import annotations

import os
import secrets
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse

KEY_NAME = "ANTHROPIC_API_KEY"
ENV_FILE = Path(os.environ.get("AGENT_ENV_FILE", ".env.local"))
_CSRF_TOKEN = secrets.token_urlsafe(16)

router = APIRouter()


def _load_env_file() -> None:
    """Load ``KEY=VALUE`` lines from ``.env.local`` into the process env.

    Runs at import so a key bootstrapped on a previous run (persisted to the
    host-mounted ``.env.local``) is available after a restart. Existing env
    values win (``setdefault``).
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


def key_is_configured() -> bool:
    """True once an ``ANTHROPIC_API_KEY`` is available to the process."""
    return bool(os.environ.get(KEY_NAME, "").strip())


def key_setup_required() -> JSONResponse | None:
    """Call at the top of ``POST /chat``.

    Returns a ``409`` pointing the chat UI at ``/setup`` when no key is
    configured, else ``None`` (proceed with the model call). The frontend turns
    the ``setup_url`` into a "Connect your API key" button.
    """
    if key_is_configured():
        return None
    return JSONResponse(
        status_code=409,
        content={"error": f"{KEY_NAME} is not configured", "setup_url": "/setup"},
    )


def _setup_enabled() -> bool:
    """Dev sandbox: on by default; ``AGENT_KEY_SETUP=0`` disables it (prod)."""
    return os.environ.get("AGENT_KEY_SETUP", "1") != "0"


_FORM_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Connect your Anthropic API key</title>
<style>
  body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 640px;
         margin: 64px auto; padding: 0 16px; color: #222; }}
  textarea {{ width: 100%; min-height: 110px; font-family: ui-monospace, monospace;
              font-size: 14px; padding: 8px; box-sizing: border-box; }}
  button {{ margin-top: 12px; padding: 8px 18px; font-size: 14px; cursor: pointer; }}
  .hint {{ color: #666; font-size: 14px; }}
  code {{ background: #f3f3f3; padding: 1px 4px; border-radius: 3px; }}
</style></head>
<body>
  <h2>Connect your Anthropic API key</h2>
  <p class="hint">Need one? Open
    <a href="https://console.anthropic.com/settings/keys" target="_blank"
       rel="noopener">console.anthropic.com/settings/keys</a> and copy a key. It
    goes from this form straight into this agent's environment (and a mode-0600
    <code>.env.local</code>) — never to the browser or the model's prompt.</p>
  <form method="POST" action="/setup">
    <input type="hidden" name="csrf" value="{csrf}">
    <textarea name="api_key" placeholder="sk-ant-..." required autofocus></textarea>
    <br><button type="submit">Save &amp; start chatting</button>
  </form>
</body></html>
"""

_DONE_HTML = """<!doctype html>
<html><body style="font-family: system-ui, sans-serif; max-width: 560px;
margin: 80px auto; padding: 0 16px;">
<h2>Key saved.</h2>
<p>You can close this tab and return to the chat — the agent can reply now.</p>
</body></html>
"""


@router.get("/setup", response_class=HTMLResponse)
def setup_form() -> HTMLResponse:
    if not _setup_enabled():
        return HTMLResponse("setup is disabled", status_code=404)
    return HTMLResponse(_FORM_HTML.format(csrf=_CSRF_TOKEN))


@router.post("/setup", response_class=HTMLResponse)
async def setup_submit(request: Request) -> HTMLResponse:
    if not _setup_enabled():
        return HTMLResponse("setup is disabled", status_code=404)
    raw = (await request.body()).decode("utf-8", errors="replace")
    fields = urllib.parse.parse_qs(raw)
    posted_csrf = (fields.get("csrf") or [""])[0]
    posted_key = (fields.get("api_key") or [""])[0].strip()
    if not secrets.compare_digest(posted_csrf, _CSRF_TOKEN) or not posted_key:
        return HTMLResponse("rejected (bad token or empty key)", status_code=403)
    os.environ[KEY_NAME] = posted_key
    _persist_key(posted_key)
    return HTMLResponse(_DONE_HTML)


def _persist_key(key: str) -> None:
    """Write ``KEY_NAME`` to ``.env.local`` at mode 0600 (best-effort).

    Replaces any existing line for the key. A read-only or absent mount just
    means the key lives for this process only — the chat still works now.
    Never logs the value.
    """
    try:
        lines: list[str] = []
        if ENV_FILE.is_file():
            lines = [
                ln
                for ln in ENV_FILE.read_text().splitlines()
                if not ln.strip().startswith(f"{KEY_NAME}=")
            ]
        lines.append(f"{KEY_NAME}={key}")
        ENV_FILE.write_text("\n".join(lines) + "\n")
        ENV_FILE.chmod(0o600)
    except OSError:
        pass  # process env still has the key; persistence is best-effort
