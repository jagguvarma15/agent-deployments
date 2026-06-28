---
id: obs.langsmith
kind: obs
implements:
  port: obs
  interface_version: "1.0"
layer: observability
provides: [tracing, llm_observability]
env_vars: [LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT, LANGCHAIN_ENDPOINT]
docker: null
probe: langsmith_workspace
bootstrap_step: bootstrap_langsmith
provisioning_time: instant
cost_tier: fixed-monthly
est_tokens: 650
card:
  name: LangSmith
  description: "Hosted LLM observability for LangChain / LangGraph apps. Auto-instruments via env vars."
  capabilities_provided: [llm_tracing, tool_call_tracing, dataset_eval]
  required_credentials: [LANGCHAIN_API_KEY]
emit_files: []
docs: |
  LangSmith hosted tracing for LangChain / LangGraph agents. Bootstrap step
  creates the project via the LangSmith SDK and writes tracing env vars to
  `.env.local`. API-key based — no local container.
tags: [observability, llm-tracing, hosted]
when_to_load: "recipe declares obs.langsmith"
---

# Capability: obs.langsmith

> Vendor reference: https://docs.smith.langchain.com — vendor docs are authoritative.

**Used for:** trace LLM calls, tool calls, and agent graph state for LangChain / LangGraph apps. Hosted-only.

## Local setup

**No docker fragment.** LangSmith is hosted. The bootstrap step contacts the LangSmith API to create or detect the project; nothing runs in compose.

## Bootstrap (post wire_credentials)

`bootstrap_langsmith` requires `LANGCHAIN_API_KEY` to be present (`wire_credentials` prompts for it). It resolves the project name from the recipe's [`bootstrap_config.langsmith`](../../recipes/SCHEMA.md#bootstrap_configlangsmith) block, falling back to `manifest.project_name`, then `default`:

```python
from langsmith import Client
client = Client(api_key=os.environ["LANGCHAIN_API_KEY"])
project_name = (
    recipe.bootstrap_config.get("langsmith", {}).get("project_name")
    or manifest.project_name
    or "default"
)
try:
    client.read_project(project_name=project_name)
except langsmith.utils.LangSmithNotFoundError:
    client.create_project(project_name=project_name)
```

The step then appends to `.env.local`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=<project_name>
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `LANGCHAIN_API_KEY` | *(secret)* | API key from https://smith.langchain.com/settings — stored via keyring |
| `LANGCHAIN_TRACING_V2` | `true` | Enables tracing globally for LangChain runtime |
| `LANGCHAIN_PROJECT` | *(project name)* | Project bucket for runs in the LangSmith UI |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | Override only if using LangSmith on-prem |

> **`LANGCHAIN_*` vs `LANGSMITH_*`.** Recent LangSmith SDKs accept `LANGSMITH_API_KEY`
> / `LANGSMITH_TRACING` / `LANGSMITH_PROJECT` / `LANGSMITH_ENDPOINT` as aliases for the
> `LANGCHAIN_*` names above. This capability standardizes on the `LANGCHAIN_*` names
> (broadest compatibility); set the `LANGSMITH_*` form too only if a newer SDK requires
> it. Connect the key + a custom project from the scaffold REPL with `/config
> LANGCHAIN_API_KEY` and `/config LANGCHAIN_PROJECT`.

## Client integration

LangSmith auto-instruments LangChain / LangGraph via env vars. No explicit client wiring required when `LANGCHAIN_TRACING_V2=true`.

**Python (manual trace if needed):**

```python
from langsmith import traceable

@traceable(name="research_step")
async def research_step(question: str) -> str:
    return await llm.ainvoke(question)
```

**TypeScript:**

```ts
import { traceable } from "langsmith/traceable";

const researchStep = traceable(
  async (question: string) => await llm.invoke(question),
  { name: "research_step" }
);
```

## Cloud / production

Same setup. Production projects typically rotate `LANGCHAIN_API_KEY` per-environment; the `secrets purge` flow handles rotation across keyring + file + .env.local.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| Traces never appear in UI | `LANGCHAIN_TRACING_V2` not set in the process | Confirm env is loaded; agent process must inherit `LANGCHAIN_TRACING_V2=true` |
| `401 Unauthorized` | Wrong workspace key | Recreate key under the workspace whose project you're tracing into |
| Project name mismatch | Recipe declared `bootstrap_config.langsmith.project_name` but env shows `default` | Re-run `bootstrap_langsmith` after the recipe edit |
| `429 Too Many Requests` | Free tier rate limit | Upgrade plan or sample traces (`LANGCHAIN_SAMPLING_RATE=0.1`) |

## See also

- [`stack/tracing-langfuse.md`](../../stack/tracing-langfuse.md) — alternative tracing stack
- [`capabilities/obs/langfuse.md`](langfuse.md) — sibling self-hosted capability
- [`cross-cutting/observability.md`](../../cross-cutting/observability.md) — observability strategy
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
