---
status: Blueprint (design spec)
languages: [python, typescript]
required_files:
  - app/main.py
  - app/agent/host.py
  - app/tools/web_search.py
  - app/tools/fetch_url.py
  - app/models/schemas.py
  - .claude/agents/researcher.md
  - tests/unit/test_schemas.py
  - tests/integration/test_subagent.py
  - tests/eval/dataset.jsonl
  - .env.example
  - pyproject.toml
  - README.md
recipe_dependencies:
  python:
    claude-agent-sdk: ">=0.2.0"
    anthropic: ">=0.69.0"
    pydantic: ">=2.5.0"
    pydantic-settings: ">=2.0.0"
    structlog: ">=24.1.0"
    httpx: ">=0.27.0"
  typescript:
    "@anthropic-ai/claude-agent-sdk": "^0.3.0"
    zod: "^3.23.0"
external_services: []
capabilities:
  - obs.langfuse
topology: single
load_list:
  - {path: ../frameworks/claude-agent-sdk.md, required: true, when: "language == 'python'"}
  - {path: ../frameworks/claude-agent-sdk-typescript.md, required: true, when: "language == 'typescript'"}
  - {path: ../patterns/react.md, required: true}
  - {path: ../patterns/routing-tool-use.md, required: true}
  - {path: ../cross-cutting/project-layout.md, required: true}
  - {path: ../stack/llm-claude.md, required: true}
  - {path: ../stack/tool-protocol-mcp.md, required: false}
  - {path: ../stack/tracing-langfuse.md, required: false, when: "capabilities contains 'obs.langfuse'"}
  - {path: ../cross-cutting/logging-structured.md, required: false}
  - {path: ../cross-cutting/testing-strategy.md, required: false}
  - {path: ../cross-cutting/eval-data.md, required: false}
  - {path: ../cross-cutting/prompt-management.md, required: false}
roles:
  - name: researcher
    description: Subagent that takes a research question and returns a list of cited findings.
    role_kind: worker
    model_hint: sonnet
    model_fallbacks: [haiku]
    tools: [web_search, fetch_url]
---

# Recipe: Claude Code Subagent

**Status:** Blueprint (design spec)

## Composes

- Framework (Py): [Claude Agent SDK](../frameworks/claude-agent-sdk.md) (`claude-agent-sdk` `>=0.2.0`)
- Framework (TS): [Claude Agent SDK (TypeScript)](../frameworks/claude-agent-sdk-typescript.md) (`@anthropic-ai/claude-agent-sdk` `^0.3.0`)
- Pattern: [ReAct](../patterns/react.md) — the SDK's default loop. Combined with [Routing / Tool use](../patterns/routing-tool-use.md) for the host's intent classification.
- Stack: [Claude LLM](../stack/llm-claude.md), optional [Langfuse](../stack/tracing-langfuse.md) for tracing, optional [MCP tool protocol](../stack/tool-protocol-mcp.md) for future tool re-use.
- Cross-cutting: [Project layout](../cross-cutting/project-layout.md), [Logging](../cross-cutting/logging-structured.md), [Testing strategy](../cross-cutting/testing-strategy.md), [Eval data](../cross-cutting/eval-data.md).

### Load list

Feed these files to your AI coding assistant to build this agent:

**Core (always load):**
- `docs/recipes/claude-code-subagent.md` — this blueprint
- `docs/frameworks/claude-agent-sdk.md` (Python) or `docs/frameworks/claude-agent-sdk-typescript.md` (TypeScript)
- `docs/patterns/react.md` — the ReAct loop the subagent runs
- `docs/patterns/routing-tool-use.md` — how the host decides what to delegate
- `docs/cross-cutting/project-layout.md` — the canonical directory tree the host CLI lives in
- `docs/stack/llm-claude.md` — Claude model selection and pricing

**Optional (load when relevant):**
- `docs/stack/tool-protocol-mcp.md` — if you plan to expose tools via MCP
- `docs/stack/tracing-langfuse.md` — if you enable `obs.langfuse`
- `docs/cross-cutting/testing-strategy.md` · `docs/cross-cutting/eval-data.md` · `docs/cross-cutting/logging-structured.md`

## What it does

A host CLI accepts a research question on the command line, spawns a Claude Code-style subagent defined in `.claude/agents/researcher.md`, lets the subagent run a ReAct loop over `web_search` and `fetch_url` tools, and prints the structured `ResearchResult` to stdout as JSON.

The point of the recipe is to demonstrate **subagent isolation**: the parent host's context window is not polluted by the subagent's verbose tool outputs, and the subagent ships with its own system prompt, model tier, and tool allowlist that the host doesn't have to specify per call. The parent process only sees the final `Finding` list.

This is the smallest end-to-end project that exercises every part of the Claude Agent SDK an in-process agent uses: `query()`, `@tool`, `ClaudeAgentOptions(subagents_dir=...)`, and at least one `PreToolUse` hook for the permission gate.

## Architecture

```
                ┌─────────────────────┐
                │  Host CLI           │   python -m app.main "<question>"
                │  (app/main.py)      │
                └──────────┬──────────┘
                           │ Question
                           ▼
                ┌─────────────────────┐
                │  Host agent         │   ClaudeAgentOptions(
                │  (app/agent/host.py)│     subagents_dir=".claude/agents",
                │                     │     hooks={"PreToolUse": gate},
                └──────────┬──────────┘   )
                           │ Agent tool: "researcher"
                           ▼
                ┌─────────────────────┐
                │  Researcher subagent│   .claude/agents/researcher.md
                │  (separate session, │   own system prompt, own model,
                │   own context)      │   own tool allowlist
                └──────────┬──────────┘
                           │ tool calls
            ┌──────────────┼──────────────┐
            ▼                             ▼
    ┌──────────────┐              ┌──────────────┐
    │  web_search  │              │  fetch_url   │
    │  (tool)      │              │  (tool)      │
    └──────────────┘              └──────────────┘
                           │ findings
                           ▼
                ┌─────────────────────┐
                │  ResearchResult     │   JSON to stdout
                │  (Pydantic / Zod)   │
                └─────────────────────┘
```

## Data Models

Pydantic v2 (Python) and Zod (TypeScript) schemas. The names are part of the contract — both the host and the subagent serialize against these.

```python
# app/models/schemas.py
from pydantic import BaseModel, Field, HttpUrl


class Question(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class Finding(BaseModel):
    claim: str = Field(description="A single factual claim derived from sources.")
    sources: list[HttpUrl] = Field(min_length=1, description="URLs that back the claim.")
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class ResearchResult(BaseModel):
    question: str
    findings: list[Finding]
    steps_used: int = Field(description="Number of agent turns the subagent consumed.")
    truncated: bool = Field(default=False, description="True when the subagent hit max_turns.")
```

```typescript
// app/models/schemas.ts
import { z } from "zod";

export const Question = z.object({
  text: z.string().min(3).max(500),
});

export const Finding = z.object({
  claim: z.string(),
  sources: z.array(z.string().url()).min(1),
  confidence: z.number().min(0).max(1).default(0.5),
});

export const ResearchResult = z.object({
  question: z.string(),
  findings: z.array(Finding),
  steps_used: z.number().int(),
  truncated: z.boolean().default(false),
});

export type ResearchResult = z.infer<typeof ResearchResult>;
```

## API Contract

CLI entry. No HTTP surface — single-process by design.

```bash
# Happy path
python -m app.main "What are the main differences between supervised and unsupervised learning?"

# Returns ResearchResult as JSON on stdout, exit code 0:
{
  "question": "...",
  "findings": [
    {"claim": "Supervised learning uses labeled training data.", "sources": ["https://..."], "confidence": 0.95}
  ],
  "steps_used": 4,
  "truncated": false
}

# Empty input: stderr + exit code 2
# Subagent truncation: result.truncated = true, exit code 0 (still a valid result)
# Tool denial via PreToolUse: stderr + exit code 1
```

TypeScript variant runs the same way via `tsx app/main.ts "<question>"`.

## Tool Specifications

Two tools. Both live under `app/tools/` so the subagent's allowlist references them by short name.

### `web_search`

```json
{
  "name": "web_search",
  "description": "Search the web for the given query. Returns up to max_results result rows as {title, url, snippet}.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "minLength": 1, "maxLength": 256},
      "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5}
    },
    "required": ["query"]
  }
}
```

### `fetch_url`

```json
{
  "name": "fetch_url",
  "description": "Fetch the body text of an absolute https URL. Returns up to 4000 characters of plain text (HTML stripped).",
  "input_schema": {
    "type": "object",
    "properties": {
      "url": {"type": "string", "format": "uri"}
    },
    "required": ["url"]
  }
}
```

The recipe ships **mock implementations** of both tools in `app/tools/`. Wiring a real search provider (Tavily, Brave Search) and a real HTTP fetch is a one-line swap inside the tool body; the contract above does not change.

## Prompt Specifications

The host has a minimal system prompt — its only job is to delegate. The subagent has the substantive prompt.

### Host system prompt (`app/agent/host.py`, ~30 words)

```text
You are a research dispatcher. When the user asks a question, invoke the researcher subagent
exactly once with the question text. Return the subagent's result verbatim.
```

### Subagent definition (`.claude/agents/researcher.md`)

```markdown
---
name: researcher
description: Answers research questions by searching, fetching sources, and synthesizing cited findings.
tools: [web_search, fetch_url]
model: sonnet
---

You answer research questions by reasoning step-by-step.

For each question:
1. Decide what subqueries would resolve the question. Plan at most three subqueries up front.
2. Call `web_search` for each subquery. Inspect the snippets.
3. For any source that looks authoritative, call `fetch_url` once to read the body.
4. Synthesize a list of Findings. Each Finding has:
   - `claim`: one short, factual sentence.
   - `sources`: at least one URL from your searches.
   - `confidence`: 0.0–1.0 — how strongly the sources back the claim.

Rules:
- Do not invent sources. A claim without a real URL is a bug; omit it.
- Do not call `fetch_url` more than 5 times total.
- If the question is ambiguous, return one Finding with `claim` asking the user to clarify and `confidence: 0.0`.

Return only the JSON list of Findings — no prose, no preamble.
```

Length and structure are deliberate: the model selection + tool allowlist live in frontmatter (the Claude Code subagent convention), the operational guidance is the body, and the rules section keeps the surface small enough to fit in the subagent's context budget alongside the question and tool results.

## Key files

| File | Responsibility |
|------|----------------|
| `app/main.py` | CLI entry — parse argv, validate `Question`, call `run_host()`, serialize `ResearchResult` to stdout. ~40 lines. |
| `app/agent/host.py` | Builds `ClaudeAgentOptions` (host system prompt, `subagents_dir=".claude/agents"`, `PreToolUse` permission gate, `max_turns=6`). Drives the SDK's `query()` async generator and unmarshals the subagent's final JSON into `ResearchResult`. ~80 lines. |
| `app/tools/web_search.py` | `@tool("web_search", ...)`. Returns mock results by default; replace the body with a real provider call when wiring. ~30 lines. |
| `app/tools/fetch_url.py` | `@tool("fetch_url", ...)`. Uses `httpx` with a 10-second timeout, strips HTML to plain text. ~30 lines. |
| `app/models/schemas.py` | The Pydantic v2 models above. Single source of truth for the result shape. |
| `.claude/agents/researcher.md` | The subagent definition above. The SDK reads it when the host invokes the `Agent` tool with `name="researcher"`. |
| `tests/unit/test_schemas.py` | Roundtrip tests for `Question`, `Finding`, `ResearchResult`. Hits the validators directly — no SDK call. |
| `tests/integration/test_subagent.py` | Uses a recorded subagent transcript (frozen JSON of message blocks) to drive the host with a stubbed `query()`. Asserts the unmarshalled `ResearchResult` shape and the permission-gate path. |
| `tests/eval/dataset.jsonl` | 10 `(question, expected_claim_substring)` rows. See [`../cross-cutting/eval-data.md`](../cross-cutting/eval-data.md) for how to grow this. |
| `.env.example` | `ANTHROPIC_API_KEY` (required) plus optional `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` when `obs.langfuse` is enabled. |
| `pyproject.toml` | Uses the pinned `recipe_dependencies.python` set above. `tool.ruff` + `tool.mypy` per the canonical [project layout](../cross-cutting/project-layout.md). |
| `README.md` | Quickstart: clone, copy `.env.example` to `.env`, `uv sync`, `uv run python -m app.main "your question"`. |

## Implementation Roadmap

1. **Scaffold the layout** per [`../cross-cutting/project-layout.md`](../cross-cutting/project-layout.md). Empty stubs for every entry in `required_files`. Confirm `uv run pytest` exits with code 5 (no tests collected) rather than an import error.
2. **Define the schemas first.** `app/models/schemas.py` (Python) and the Zod equivalents (TypeScript). Write `tests/unit/test_schemas.py` against them. This is your contract for everything downstream.
3. **Stub the two tools.** `web_search` and `fetch_url` returning hardcoded results. The mock outputs must satisfy the JSON Schema you wrote in the Tool Specifications section above.
4. **Drop in the subagent definition** at `.claude/agents/researcher.md` exactly as written above. Resist the temptation to over-prompt; the rules section is load-bearing.
5. **Build the host.** `ClaudeAgentOptions(system_prompt=..., subagents_dir=".claude/agents", hooks={"PreToolUse": gate}, max_turns=6)`, then drive `query()` and unmarshal the trailing assistant text block as `ResearchResult`. The PreToolUse hook denies any tool whose name is not in `{"web_search", "fetch_url", "Agent"}`.
6. **Smoke test it manually.** `python -m app.main "What is MCP?"` with a real `ANTHROPIC_API_KEY`. Confirm at least one `web_search` call and a populated `findings` list.
7. **Write the integration test** by recording one real subagent run, redacting URLs, and replaying via a stubbed `query()` so the test runs offline. See [`../cross-cutting/testing-strategy.md`](../cross-cutting/testing-strategy.md) for the three-tier split.
8. **Seed the eval dataset.** 10 rows is enough to start. Grow it per [`../cross-cutting/eval-data.md`](../cross-cutting/eval-data.md) once the agent is stable.

## Environment & Deployment

`.env.example`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional — enabled when the recipe is generated with capability obs.langfuse
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
```

No `docker-compose.yml`. The agent is a single Python process. The optional Langfuse capability is consumed remotely (cloud or self-hosted) — see [`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md).

MCP integration is a future extension: the same tools can be re-exposed via an MCP server entry point so other Claude clients (Claude Code, Claude Desktop) can call them. See [`../stack/tool-protocol-mcp.md`](../stack/tool-protocol-mcp.md) for the protocol. Out of scope for the initial recipe.

## Test Strategy

Three tiers per [`../cross-cutting/testing-strategy.md`](../cross-cutting/testing-strategy.md).

- **Unit** (`tests/unit/`) — schema roundtrip; tool input-shape validation; PreToolUse gate logic in isolation. No SDK call. Must run in under 2 seconds.
- **Integration** (`tests/integration/`) — host wired to a stubbed `query()` that yields a recorded message stream. Asserts the `ResearchResult` shape, that the gate allows `web_search` / `fetch_url` / `Agent` and denies anything else, and that `truncated=True` propagates when the stream ends mid-loop.
- **Eval** (`tests/eval/`) — see Eval Dataset below.

The integration test deliberately avoids hitting the real Claude API; that's the eval tier's job. Stubbing `query()` lets the host's gate / unmarshal / error-path logic stay in CI without an `ANTHROPIC_API_KEY` secret.

## Eval Dataset

10 inline golden cases. Each row maps a question to a substring the expected `findings[]` must include.

```jsonl
{"id": "ccs-001", "category": "definition", "question": "What is MCP?", "expected_answer_contains": ["Model Context Protocol", "tools", "Anthropic"]}
{"id": "ccs-002", "category": "comparison", "question": "What are the main differences between supervised and unsupervised learning?", "expected_answer_contains": ["labeled", "unlabeled", "clustering"]}
{"id": "ccs-003", "category": "comparison", "question": "Compare RAG and fine-tuning as LLM customization strategies.", "expected_answer_contains": ["retrieval", "fine-tuning", "training"]}
{"id": "ccs-004", "category": "factual", "question": "When did the Claude Agent SDK first ship?", "expected_answer_contains": ["Anthropic"]}
{"id": "ccs-005", "category": "factual", "question": "What programming language is the Claude Agent SDK Python package written in?", "expected_answer_contains": ["Python"]}
{"id": "ccs-006", "category": "refusal", "question": "What will the next major Anthropic model release contain?", "expected_answer_contains": ["don't know", "cannot determine", "not available"]}
{"id": "ccs-007", "category": "multi-source-synthesis", "question": "Why is prompt caching useful in production LLM apps?", "expected_answer_contains": ["latency", "cost", "cache"]}
{"id": "ccs-008", "category": "clarification", "question": "How does it work?", "expected_clarification": true, "expected_answer_contains": ["clarify", "specific"]}
{"id": "ccs-009", "category": "tool-sequencing", "question": "Find a tutorial for the Claude Agent SDK and summarize the first three steps.", "expected_tool_calls": ["web_search", "fetch_url"], "expected_answer_contains": ["step"]}
{"id": "ccs-010", "category": "edge-case", "question": "x", "expected_clarification": true, "expected_answer_contains": ["clarify", "more detail"]}
```

See [`../cross-cutting/eval-data.md`](../cross-cutting/eval-data.md) for generation + curation patterns.

## Design Decisions

- **Subagent vs inline tool loop.** An inline tool loop (single agent with `web_search` + `fetch_url` directly attached) would be ~30 fewer lines and faster. The subagent split exists because it isolates the noisy tool-result history from the host's context — for a recipe whose pedagogical point is "this is how a Claude Code subagent works", the isolation *is* the lesson. For a real research agent where you don't care about isolation, drop the subagent and keep the tools on the host.
- **Claude Agent SDK over raw `anthropic.Anthropic().messages.create()`.** The agent loop, tool registry, hook plumbing, and subagent invocation are the SDK's value-add. Hand-rolling them is a documented anti-pattern in the SDK guide ([`../frameworks/claude-agent-sdk.md#anti-patterns`](../frameworks/claude-agent-sdk.md#anti-patterns)). For a one-shot summarize-this-document call, the raw SDK is fewer moving parts; this recipe is the case where the SDK earns its keep.
- **`max_turns=6` as the cap.** Two for the host's invoke-subagent + receive-result cycle, four for the subagent's research loop. Higher caps invite the subagent to keep searching past diminishing returns; lower caps strand it before it can synthesize.
- **Mock tool bodies.** Reading from a real search provider on first run pushes the recipe into "you need API keys for two services to try it" territory. Mocks let `python -m app.main "What is MCP?"` produce a meaningful demo with only `ANTHROPIC_API_KEY` set. Wiring the real provider is documented as a one-line swap.
- **PreToolUse gate over a model-side allowlist.** The subagent's frontmatter already declares `tools: [web_search, fetch_url]`, but the host's `PreToolUse` hook is the durable enforcement. If a future version of the SDK changes how frontmatter allowlists are honored, the hook still prevents a misconfigured subagent from invoking shell-exec or filesystem-write tools.
- **`obs.langfuse` is optional, not default.** A first-run user shouldn't need a tracing backend account. The capability is wired so a generator with `obs.langfuse` enabled gets the integration but the no-capability variant runs hermetically.

## Reference Implementation

This is a design-spec recipe. The frontmatter declares `status: Blueprint (design spec)` because no end-to-end runnable ships in this PR — the prompts, schemas, and tool contracts above are the contract; the actual file bodies are written when the recipe is scaffolded.

A future PR can promote this to `Blueprint (validated)` once:

- `app/main.py`, `app/agent/host.py`, `app/tools/*.py`, and `app/models/schemas.py` exist as runnable code.
- The integration test in `tests/integration/test_subagent.py` runs offline against a recorded subagent transcript.
- The eval dataset is curated by hand (the 10 inline rows above are starter prompts, not goldens).
- A TypeScript counterpart at parity ships under `apps/ts/` or as a sibling project.

The TypeScript variant follows the same structure: `app/main.ts` invokes `query` from `@anthropic-ai/claude-agent-sdk` with `ClaudeAgentOptions({systemPrompt, subagentsDir, hooks, maxTurns})`, the subagent definition is byte-identical (Claude Code reads the same `.claude/agents/researcher.md` regardless of language), and the Zod schemas in `app/models/schemas.ts` carry the same field set as the Python ones. See [`../frameworks/claude-agent-sdk.md#typescript-variant`](../frameworks/claude-agent-sdk.md#typescript-variant) for the SDK calls in TS.
