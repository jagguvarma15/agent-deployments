---
id: guardrail.llama-guard
kind: guardrail
implements:
  port: guardrail
  interface_version: "1.0"
layer: agent
provides: [input_classification, output_classification, jailbreak_detection]
env_vars: [TOGETHER_API_KEY]
docker: null
probe: llama_guard_classify
bootstrap_step: null
provisioning_time: instant
cost_tier: per-call
est_tokens: 600
card:
  name: Llama Guard 3 (via Together AI)
  description: "Meta's Llama Guard 3 (8B) safety classifier for input/output policy enforcement and jailbreak detection."
  capabilities_provided: [safety_classification, jailbreak_detection, dual_llm_split]
  required_credentials: [TOGETHER_API_KEY]
emit_files: []
docs: |
  Meta's Llama Guard 3 (8B) as the safety-classifier modifier wrapping the
  agent's input and output surfaces. Default impl calls Llama Guard via
  Together AI's hosted inference. Recipes wire it via
  `guardrails: [guardrail.llama-guard]`.
tags: [guardrail, safety, llama]
when_to_load: "recipe declares guardrail.llama-guard"
---

# Capability: guardrail.llama-guard

> First-run setup: [`getting-started/llama-guard.md`](../../getting-started/llama-guard.md). Vendor: https://llama.meta.com/docs/model-cards-and-prompt-formats/llama-guard-3.

**Used for:** Classifying agent inputs and outputs for safety violations (violence, sexual content, hate, self-harm, criminal planning, …) before they reach the LLM or the user.

## Wiring

```yaml
# In a recipe's frontmatter:
guardrails: [guardrail.llama-guard]
```

The scaffold emits two hooks in the generated project:

- `pre_llm_call(messages) → allow | deny(reason)` — input classifier
- `post_llm_call(response) → allow | deny(reason)` — output classifier

Denials short-circuit the agent loop and return a structured safety-violation error to the caller (HTTP 403 with `safety.category` in the body).

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `TOGETHER_API_KEY` | *(prompted)* | Together AI API key — stored via keyring |

## Client integration

**Python (together):**

```python
from together import AsyncTogether

client = AsyncTogether(api_key=os.environ["TOGETHER_API_KEY"])

async def classify(messages: list[dict]) -> tuple[bool, str | None]:
    resp = await client.chat.completions.create(
        model="meta-llama/Llama-Guard-3-8B",
        messages=messages,
    )
    output = resp.choices[0].message.content.strip()
    if output.startswith("safe"):
        return True, None
    # "unsafe\nS1" — S1..S14 are MLCommons taxonomy categories
    _, category = output.split("\n", 1)
    return False, category
```

**TypeScript (together-ai):**

```ts
import Together from "together-ai";

const client = new Together({ apiKey: process.env.TOGETHER_API_KEY! });

async function classify(messages: Array<{role: string, content: string}>) {
  const resp = await client.chat.completions.create({
    model: "meta-llama/Llama-Guard-3-8B",
    messages,
  });
  const output = resp.choices[0].message.content.trim();
  if (output.startsWith("safe")) return { allow: true, category: null };
  const [, category] = output.split("\n");
  return { allow: false, category };
}
```

## Probe

`llama_guard_classify` sends a benign message and asserts the classifier returns `safe`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Wrong / expired key | Recreate at https://api.together.ai/settings/api-keys |
| `404 model not found` | Together rotated the model id | Check current id at https://api.together.ai/models; update the capability's model reference |
| Classifier denies benign input | False positive on Llama Guard's taxonomy | Switch to `guardrail.openai-moderation` for a different taxonomy, or refine the system prompt |
| Latency >800ms per call | Cold start | Together caches warm pods; latency drops after a few calls. For tighter SLO, swap to a self-hosted vLLM instance |

## See also

- [`modifiers/guardrails/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/modifiers/guardrails/overview.md) — pattern guidance on dual-LLM safety
- [`cross-cutting/security-hardening.md`](../../cross-cutting/security-hardening.md) — broader security posture
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
