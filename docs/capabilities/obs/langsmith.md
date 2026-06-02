---
id: obs.langsmith
kind: obs
provides: [tracing, llm_observability]
env_vars: [LANGCHAIN_API_KEY, LANGCHAIN_TRACING_V2, LANGCHAIN_PROJECT, LANGCHAIN_ENDPOINT]
docker: null
probe: langsmith_workspace
bootstrap_step: bootstrap_langsmith
emit_files: []
docs: |
  LangSmith hosted tracing for LangChain / LangGraph agents. Bootstrap step
  creates the project via the LangSmith SDK and writes tracing env vars to
  `.env.local`. API-key based — no local container.
---

# Capability: obs.langsmith

> Deep reference: https://docs.smith.langchain.com — vendor docs are authoritative.

**Used for:** trace LLM calls, tool calls, and agent graph state for LangChain / LangGraph apps. Hosted (no self-hosted option in v1 of this capability).

## Why pick this

The lowest-friction tracing for LangGraph projects — `LANGCHAIN_TRACING_V2=true` and the framework auto-instruments everything. Pick `obs.langfuse` instead if you want self-hosted, or `obs.grafana-stack` for OTel-based tracing across heterogeneous services.

## Local setup

**No docker fragment.** LangSmith is hosted-only in this capability. The bootstrap step contacts the LangSmith API to create or detect the project; nothing runs in compose.

## Bootstrap (post wire_credentials)

`bootstrap_langsmith` requires `LANGCHAIN_API_KEY` to be present (the `wire_credentials` step prompts for it if missing and stores via the existing keyring layer). It then resolves the project name from the recipe's [`bootstrap_config.langsmith`](../../recipes/SCHEMA.md#bootstrap_configlangsmith) block, falling back to `manifest.project_name`, then `default`:

```python
from langsmith import Client
client = Client(api_key=os.environ["LANGCHAIN_API_KEY"])
project_name = (
    recipe.bootstrap_config.get("langsmith", {}).get("project_name")
    or manifest.project_name
    or "default"
)
try:
    client.read_project(project_name=project_name)         # exists → DONE
except langsmith.utils.LangSmithNotFoundError:
    client.create_project(project_name=project_name)       # create → DONE
```

The step then appends to `.env.local`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=<project_name>
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

Optional dep in the generated project: `langsmith` (auto-pulled by `langchain` / `langgraph`).

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `LANGCHAIN_API_KEY` | *(secret)* | API key from https://smith.langchain.com/settings — stored via keyring |
| `LANGCHAIN_TRACING_V2` | `true` | Enables tracing globally for LangChain runtime |
| `LANGCHAIN_PROJECT` | *(project name)* | Project bucket for runs in the LangSmith UI |
| `LANGCHAIN_ENDPOINT` | `https://api.smith.langchain.com` | Override only if using LangSmith on-prem |

## Cloud / production

Same setup. Production projects typically rotate `LANGCHAIN_API_KEY` per-environment; the existing `secrets purge` flow handles rotation across keyring + file + .env.local.

## When to swap it

- **→ `obs.langfuse`** if self-hosting is required, or if you want OSS tracing without a SaaS dependency.
- **→ `obs.grafana-stack`** if your trace target includes non-LLM services and you want OTel everywhere.

## See also

- `stack/tracing-langfuse.md` — alternative tracing stack
- `capabilities/obs/langfuse.md` — sibling self-hosted capability
- `cross-cutting/observability.md` — observability strategy doc
