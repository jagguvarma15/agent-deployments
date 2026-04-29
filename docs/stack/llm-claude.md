# Stack pick: Anthropic Claude

**Choice:** Claude Sonnet 4.6 (default), Haiku 4.5 (cheap/fast paths)
**Used for:** Primary LLM for all agent reasoning, tool use, and generation

## Why this over alternatives

| Option | Why not |
|--------|---------|
| OpenAI GPT-4.1/5 | Strong alternative; available via `litellm` (Py) or Vercel AI SDK providers (TS) as a one-line swap |
| Google Gemini | Competitive on long context, but weaker tool-use ergonomics for agentic patterns |
| Open-source (Llama, Mistral) | Viable for cost-sensitive production; needs self-hosting infra not in scope for this repo |

Claude was chosen for strong tool use, native MCP support, and long context (200K tokens).

## Model selection

| Model | Use case | Cost profile |
|-------|----------|-------------|
| `claude-sonnet-4-6-20250514` | Default for all agent reasoning, tool use, generation | Mid-range |
| `claude-haiku-4-5-20251001` | Classification, routing, simple extraction | Low cost, fast |
| `claude-opus-4-6` | Complex multi-step reasoning, evaluation | Higher cost |

Each prototype sets the model in its settings:

```python
# Python (settings.py)
qa_model: str = "claude-sonnet-4-6-20250514"
```

```typescript
// TypeScript (config.ts)
qaModel: "claude-sonnet-4-6-20250514",
```

## Integration pattern

### Python (via Pydantic AI)

```python
from pydantic_ai import Agent

agent = Agent(
    "anthropic:claude-sonnet-4-6-20250514",
    system_prompt="You are a helpful assistant.",
)
result = await agent.run("What is MCP?")
```

### Python (via LangChain)

```python
from langchain_anthropic import ChatAnthropic

llm = ChatAnthropic(model="claude-sonnet-4-6-20250514")
result = await llm.ainvoke("What is MCP?")
```

### TypeScript (via Vercel AI SDK)

```typescript
import { anthropic } from "@ai-sdk/anthropic";
import { generateText } from "ai";

const result = await generateText({
  model: anthropic("claude-sonnet-4-6-20250514"),
  prompt: "What is MCP?",
});
```

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `ANTHROPIC_API_KEY` | (required) | API key for Anthropic |
| `QA_MODEL` / `RESEARCH_MODEL` | `claude-sonnet-4-6-20250514` | Model ID per prototype |

## Swapping to OpenAI

### Python (via litellm)

Change the model string -- `litellm` routes to the right provider:

```python
agent = Agent("openai:gpt-4.1", system_prompt="...")
```

Set `OPENAI_API_KEY` in `.env`.

### TypeScript (via Vercel AI SDK)

```typescript
import { openai } from "@ai-sdk/openai";

const result = await generateText({
  model: openai("gpt-4.1"),
  prompt: "What is MCP?",
});
```

This is a **single-file swap** (model string + env var).

## Where used in repo

Every prototype uses Claude as the primary LLM. The model ID is configurable per prototype via settings/config, defaulting to Sonnet 4.6.
