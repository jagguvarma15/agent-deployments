---
tags: [llm, local, vllm]
when_to_load: "recipe.runtime_mode == 'local_only'"
---

# LLM — local vLLM

Self-hosted Llama 3 / Qwen / Mistral served by [vLLM](https://docs.vllm.ai). The canonical `local_only` swap target for recipes that default to Anthropic Claude.

## When recipes pick this

A recipe declares it as a runtime-mode swap:

```yaml
runtime_modes:
  local_only:
    description: "Self-hosted vLLM, no Anthropic key needed."
    swaps:
      stack/llm-claude: stack/llm-local-vllm
```

The consumer applies the swap by:

1. Adding a `vllm` service to compose (image `vllm/vllm-openai:latest`, GPU `count: 1`).
2. Setting `OPENAI_API_BASE` to `http://vllm:8000/v1` and `OPENAI_API_KEY` to a dummy value.
3. Rewriting the agent code's LLM client to point at `OPENAI_API_BASE` with the OpenAI-compatible SDK.

## Models

| Model | Min GPU | Quality vs Claude Sonnet | Recipe fits |
|---|---|---|---|
| `meta-llama/Llama-3.1-8B-Instruct` | 1× L4 (24GB) | -15% on agentic benchmarks | small-context agents |
| `meta-llama/Llama-3.1-70B-Instruct-AWQ` | 1× A100 (80GB) | -5% | most recipes |
| `Qwen/Qwen2.5-72B-Instruct-AWQ` | 1× A100 (80GB) | parity on routing/RAG | RAG / routing recipes |

Pin the model in the vLLM Compose env via `MODEL=meta-llama/Llama-3.1-70B-Instruct-AWQ`.

## Local setup

```yaml
# docker-compose.override.yml (or recipe's local_only overlay)
services:
  vllm:
    image: vllm/vllm-openai:latest
    ports: ["8001:8000"]
    environment:
      MODEL: meta-llama/Llama-3.1-70B-Instruct-AWQ
      MAX_MODEL_LEN: "8192"
    volumes:
      - hf_cache:/root/.cache/huggingface
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: ["gpu"]
              count: 1
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:8000/v1/models || exit 1"]
      interval: 30s
      timeout: 5s
      retries: 10

volumes:
  hf_cache: {}
```

Bring it up:

```bash
docker compose --profile local-only up -d vllm
# First boot pulls the model (~30 GB for 70B AWQ) — allow ~10 minutes.
```

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `OPENAI_API_BASE` | `http://vllm:8000/v1` | Where the agent code points its LLM client |
| `OPENAI_API_KEY` | `local` | vLLM ignores it but the OpenAI SDK requires *some* value |
| `MODEL` | `meta-llama/Llama-3.1-70B-Instruct-AWQ` | HuggingFace model id served by vLLM |

## Client integration

The OpenAI-compatible SDK works against vLLM unchanged — just swap the base URL.

**Python:**

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "local"),
    base_url=os.environ["OPENAI_API_BASE"],
)
resp = await client.chat.completions.create(
    model=os.environ["MODEL"],
    messages=[{"role": "user", "content": "smoke test"}],
)
print(resp.choices[0].message.content)
```

**TypeScript:**

```ts
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY || "local",
  baseURL: process.env.OPENAI_API_BASE,
});
const resp = await client.chat.completions.create({
  model: process.env.MODEL!,
  messages: [{ role: "user", content: "smoke test" }],
});
```

## When to swap back to Claude

- Quality drops on agentic tasks where multi-step reasoning matters (planning, code review).
- The 70B model needs >80 GB VRAM at FP16; AWQ quantization fits in 48 GB but with -1-2 quality points.
- Latency p99 is 3-5× higher than Anthropic API at small concurrency.

For development on a single GPU, vLLM + Llama-3.1-70B-AWQ is the strongest fully-local pick. For production agentic workloads, the canonical pick remains Anthropic Claude ([`llm-claude.md`](llm-claude.md)).

## See also

- [`stack/llm-claude.md`](llm-claude.md) — canonical (Anthropic) pick
- [`cross-cutting/model-routing.md`](../cross-cutting/model-routing.md) — runtime model selection
- vLLM docs: https://docs.vllm.ai
