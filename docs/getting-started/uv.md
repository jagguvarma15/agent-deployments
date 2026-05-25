# uv

> Fast Python package + environment manager from Astral. Replaces `pip`, `pip-tools`, `virtualenv`, and (mostly) `pyenv` with a single tool.

**Signup**: not required.

## Install

```bash
# Unix (macOS, Linux, WSL)
curl -LsSf https://astral.sh/uv/install.sh | sh

# macOS via Homebrew
brew install uv

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

After install: open a new shell so `~/.local/bin` is on `PATH`.

## Verify

```bash
uv --version          # → uv 0.4.x or newer
```

`agent-scaffold doctor` requires uv ≥0.4.

## Why uv (vs pip + venv)

- **10–100× faster** dependency resolution and install
- **One tool**: `uv add`, `uv sync`, `uv run`, `uv tool install`, `uv python install`
- **Reproducible**: writes `uv.lock`; deterministic across machines
- **No global state**: each project has an isolated `.venv`; `uv run` activates it for you

## Project commands

```bash
uv sync                          # install everything from uv.lock
uv add pydantic redis            # add deps + update lock
uv add --dev pytest ruff         # add dev deps
uv run pytest                    # run a command inside the project venv
uv run python -m agent_scaffold  # works without explicit `source .venv/bin/activate`
uv tool install ruff             # install a CLI tool globally (per user)
uv python install 3.12           # manage Python versions
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `command not found: uv` after install | Shell hasn't picked up `~/.local/bin` | Open a new terminal or `source ~/.zshrc` / `~/.bashrc` |
| `No write permission to ~/.local` | Restricted user | Re-run with `--installer no-modify-path` and add the bin dir manually |
| `Failed to resolve` on a private index | Missing index URL | Set `UV_EXTRA_INDEX_URL` or `--index-url` flag |
| Apple Silicon: wheels missing | Some packages only publish `x86_64` | Allow source builds: `uv sync --no-binary <package>` |
| `Lock file is out of sync` | `pyproject.toml` changed without `uv sync` | Run `uv sync` (regenerates lock as needed) |

## See also

- Upstream docs: https://docs.astral.sh/uv/
- [`docs/getting-started/anthropic.md`](anthropic.md) — for `ANTHROPIC_API_KEY`
