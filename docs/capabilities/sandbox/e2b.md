---
id: sandbox.e2b
kind: sandbox
provides: [code_execution, isolated_runtime]
env_vars: [E2B_API_KEY]
docker: null
probe: e2b_session_open
bootstrap_step: null
emit_files: []
docs: |
  E2B Code Interpreter — hosted sandbox that runs LLM-emitted code in an
  isolated container. The agent calls `run_code(language, source)`; E2B
  returns stdout, stderr, file artifacts, and any uncaught exceptions. Used
  when recipes need the agent to author and execute code (data analysis,
  code-review repro steps, plotting). Recipes wire it via the recipe's
  `sandbox: sandbox.e2b` field; the scaffold prompts for the API key.
---

# Capability: sandbox.e2b

> First-run setup: [`getting-started/e2b.md`](../../getting-started/e2b.md). Vendor: https://e2b.dev.

**Used for:** Running LLM-emitted code in an isolated container without standing up sandboxing infrastructure.

## Why pick this

E2B is the fastest path from "agent emits code" to "code ran in a clean container, here are the artifacts." Saves implementing seccomp/firejail/Docker-in-Docker isolation, file-system quotas, and a code-output protocol. Trades vendor lock-in + per-session cost for that.

For self-hosted alternatives, `sandbox.firecracker` (planned) wraps Firecracker microVMs. For local-only dev, `sandbox.local-docker` (planned) runs a disposable container per call.

## Wiring

```yaml
# In a recipe's frontmatter:
sandbox: sandbox.e2b
```

The agent calls `run_code` (a tool the scaffold wires automatically when `sandbox:` is set). Code runs in an E2B session with a per-session timeout; results stream back as observation events.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `E2B_API_KEY` | *(prompted)* | E2B API key — stored via keyring |

## Probe

`e2b_session_open` opens a session, executes `1 + 1`, asserts `2` in stdout, and closes. Run by `agent-scaffold doctor`.

## When to swap it

- **→ `sandbox.firecracker`** — self-hosted microVMs for compliance / data residency.
- **→ `sandbox.local-docker`** — local Docker-in-Docker for offline dev.

## See also

- [`cross-cutting/sandboxed-execution.md`](../../cross-cutting/security-hardening.md) — execution-isolation policy.
- [`vendored/blueprints/foundations/sandboxed-execution.md`](../../../vendored/blueprints/foundations/sandboxed-execution.md) — pattern-level guidance.
