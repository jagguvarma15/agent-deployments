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
est_tokens: 850
card:
  name: LangSmith
  description: "Hosted LLM observability. Auto-instruments LangChain/LangGraph via env vars; any other framework must add the langsmith SDK and wrap its LLM client."
  capabilities_provided: [llm_tracing, tool_call_tracing, dataset_eval]
  required_credentials: [LANGCHAIN_API_KEY]
emit_files: []
docs: |
  LangSmith hosted tracing for LangChain / LangGraph agents. Bootstrap step
  creates the project via the LangSmith SDK and writes tracing env vars to
  `.env.local`. API-key based — no local container.
tags: [observability, llm-tracing, hosted]
when_to_load: "recipe declares obs.langsmith"
stack_docs:
  - stack/tracing-langfuse.md
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

**Env vars alone emit nothing.** The four `LANGCHAIN_*` vars only configure the
LangSmith SDK — a trace appears only when the process runs instrumented code.

**Generator requirement (hard):** when the recipe's framework is not
LangChain / LangGraph, the generated project MUST add the `langsmith` package
to its dependencies and wrap its LLM client as shown below. A project that
only sets env vars ships a silent no-op.

### What to capture

- **One root run per user request** — decorate the request handler (or the one
  function all handlers funnel through) with `@traceable(run_type="chain")`.
  Give it a stable `name`; attach `metadata` (session / user id) and `tags`
  (environment) where available.
- **Every LLM call** — via the wrapped client. Model, prompts, token usage,
  and latency are captured automatically and nest under the root run.
- **Every tool call** — `@traceable(run_type="tool")` on each tool function.
- **Retrieval calls** — `@traceable(run_type="retriever")` on vector-store /
  search lookups so hit lists are inspectable per run.
- **Errors** — exceptions raised inside a traced function are recorded on that
  run and propagate up the run tree; don't swallow them below the decorator.

Valid `run_type` values: `chain`, `llm`, `tool`, `retriever`, `embedding`,
`prompt`, `parser`. All decorators and the wrapper are safe no-ops when
`LANGCHAIN_TRACING_V2` / `LANGSMITH_TRACING` is not `"true"`, so instrumented
code ships safely with tracing off.

### How, per framework

**LangChain / LangGraph (Python or TS):** auto-instruments via the env vars.
Nothing to add — `langsmith` ships as a dependency of `langchain-core`.

**Pydantic AI / raw Anthropic SDK (Python):** add `langsmith` to the project
dependencies (`langsmith>=0.9,<1`), wrap the (async) Anthropic client, and
hand it to the model:

```python
from anthropic import AsyncAnthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic
from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.providers.anthropic import AnthropicProvider

client = wrap_anthropic(AsyncAnthropic())  # every messages.create is traced
agent = Agent(
    AnthropicModel(model_name, provider=AnthropicProvider(anthropic_client=client)),
    system_prompt=...,
)

@traceable(run_type="chain", name="research")  # root run per request
async def handle(question: str) -> str:
    result = await agent.run(question)
    return result.output

@traceable(run_type="tool")  # one per tool
async def web_search(query: str) -> str: ...
```

Raw SDK is the same wrapper: `client = wrap_anthropic(Anthropic())` (or
`AsyncAnthropic()`), then call `client.messages.create(...)` as normal.

**TypeScript (non-LangChain):** add `langsmith`, wrap the SDK:

```ts
import Anthropic from "@anthropic-ai/sdk";
import { wrapSDK } from "langsmith/wrappers";
import { traceable } from "langsmith/traceable";

const client = wrapSDK(new Anthropic());
const handle = traceable(
  async (question: string) => { /* client.messages.create(...) */ },
  { name: "research", run_type: "chain" }
);
```

### Compose contract

The app service's `environment:` block must declare all four vars —
`LANGCHAIN_API_KEY` in the **no-value form** (host passthrough; never give a
secret a default), the three non-secret vars with defaulted interpolation:

```yaml
environment:
  LANGCHAIN_API_KEY:
  LANGCHAIN_TRACING_V2: ${LANGCHAIN_TRACING_V2:-false}
  LANGCHAIN_PROJECT: ${LANGCHAIN_PROJECT:-<project-name>}
  LANGCHAIN_ENDPOINT: ${LANGCHAIN_ENDPOINT:-https://api.smith.langchain.com}
```

## Cloud / production

Same setup. Production projects typically rotate `LANGCHAIN_API_KEY` per-environment; the `secrets purge` flow handles rotation across keyring + file + .env.local.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| Traces never appear in UI | App has no instrumentation (non-LangChain framework without the `langsmith` wrapper) | Add the dependency and wrap the client (see Client integration) |
| Traces never appear in UI | `LANGCHAIN_TRACING_V2` not set in the process | Confirm env is loaded; agent process must inherit `LANGCHAIN_TRACING_V2=true` |
| `401 Unauthorized` | Wrong workspace key | Recreate key under the workspace whose project you're tracing into |
| Project name mismatch | Recipe declared `bootstrap_config.langsmith.project_name` but env shows `default` | Re-run `bootstrap_langsmith` after the recipe edit |
| `429 Too Many Requests` | Free tier rate limit | Upgrade plan or sample traces (`LANGCHAIN_SAMPLING_RATE=0.1`) |

## See also

- [`stack/tracing-langfuse.md`](../../stack/tracing-langfuse.md) — alternative tracing stack
- [`capabilities/obs/langfuse.md`](langfuse.md) — sibling self-hosted capability
- [`cross-cutting/observability.md`](../../cross-cutting/observability.md) — observability strategy
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
