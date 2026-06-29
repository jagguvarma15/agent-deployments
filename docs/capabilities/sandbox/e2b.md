---
id: sandbox.e2b
kind: sandbox
implements:
  port: sandbox
  interface_version: "1.0"
layer: agent
provides: [code_execution, isolated_runtime]
env_vars: [E2B_API_KEY]
docker: null
probe: e2b_session_open
bootstrap_step: null
provisioning_time: ~5s
cost_tier: per-call
est_tokens: 550
card:
  name: E2B Code Interpreter
  description: "Hosted sandbox running LLM-emitted code in an isolated container with file artifacts."
  capabilities_provided: [code_execution, isolated_runtime, file_artifacts]
  required_credentials: [E2B_API_KEY]
emit_files: []
docs: |
  E2B Code Interpreter — hosted sandbox that runs LLM-emitted code in an
  isolated container. Recipes wire it via `sandbox: sandbox.e2b`; the
  scaffold prompts for the API key.
tags: [sandbox, code-execution, hosted]
when_to_load: "recipe declares sandbox.e2b"
---

# Capability: sandbox.e2b

> First-run setup: [`getting-started/e2b.md`](../../getting-started/e2b.md). Vendor: https://e2b.dev.

**Used for:** Running LLM-emitted code in an isolated container with stdout/stderr capture, file artifacts, and per-session lifecycle.

## Local setup

No container — E2B sessions are hosted. Add the E2B SDK to the generated project:

- Python: `e2b-code-interpreter`
- TypeScript: `@e2b/code-interpreter`

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

## Client integration

**Python (e2b-code-interpreter):**

```python
from e2b_code_interpreter import AsyncSandbox

async with await AsyncSandbox.create(api_key=os.environ["E2B_API_KEY"]) as sbx:
    execution = await sbx.run_code("import pandas as pd; pd.DataFrame({'a':[1,2,3]}).to_csv('/tmp/out.csv', index=False); 'done'")
    print(execution.text)  # 'done'

    # Read back artifacts
    out_csv = await sbx.files.read("/tmp/out.csv")
    print(out_csv)
```

**TypeScript (@e2b/code-interpreter):**

```ts
import { Sandbox } from "@e2b/code-interpreter";

const sbx = await Sandbox.create({ apiKey: process.env.E2B_API_KEY! });
try {
  const exec = await sbx.runCode(
    `import pandas as pd
pd.DataFrame({"a": [1,2,3]}).to_csv("/tmp/out.csv", index=False)
"done"`
  );
  console.log(exec.text);

  const out = await sbx.files.read("/tmp/out.csv");
  console.log(out);
} finally {
  await sbx.kill();
}
```

## Probe

`e2b_session_open` opens a session, executes `1 + 1`, asserts `2` in stdout, and closes. Run by `agent-scaffold doctor`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Wrong / expired API key | Recreate at https://e2b.dev; rotate via keyring |
| Session timeout mid-run | Default 5-min cap | Raise via `Sandbox.create(timeout=600)` or upgrade tier |
| `ModuleNotFoundError` in sandbox | Sandbox is clean Python — package not installed | Run `await sbx.run_code("!pip install <pkg>")` first, or use `!pip install -q` inline |
| Files written but not readable later | Session ended; sandboxes are ephemeral | Read files within the same session, or upload via `sbx.files.write` then read out |

## See also

- [`cross-cutting/security-hardening.md`](../../cross-cutting/security-hardening.md) — execution-isolation policy
- [`foundations/sandboxed-execution.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/sandboxed-execution.md) — pattern-level guidance
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
