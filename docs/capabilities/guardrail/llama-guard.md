---
id: guardrail.llama-guard
kind: guardrail
provides: [input_classification, output_classification, jailbreak_detection]
env_vars: [TOGETHER_API_KEY]
docker: null
probe: llama_guard_classify
bootstrap_step: null
emit_files: []
docs: |
  Meta's Llama Guard 3 (8B) as the safety-classifier modifier wrapping the
  agent's input and output surfaces. The default impl calls Llama Guard via
  Together AI's hosted inference (`together.xyz/models/meta-llama/Llama-Guard-3-8B`).
  Recipes wire it via `guardrails: [guardrail.llama-guard]`. The scaffold
  emits an input-classifier and output-classifier hook on every recipe that
  declares it. For self-hosting, swap to `guardrail.llama-guard-local` (planned)
  which runs the model under vLLM.
---

# Capability: guardrail.llama-guard

> First-run setup: [`getting-started/llama-guard.md`](../../getting-started/llama-guard.md). Vendor: https://llama.meta.com/docs/model-cards-and-prompt-formats/llama-guard-3.

**Used for:** Classifying agent inputs and outputs for safety violations (violence, sexual content, hate, self-harm, criminal planning, …) before they reach the LLM or the user.

## Why pick this

Llama Guard 3 is the strongest open-weights safety classifier as of 2026 — outperforms GPT-4o on the MLCommons taxonomy at a fraction of the cost. The hosted-via-Together default avoids GPU ops; the self-host alternative (planned) avoids the SaaS dependency.

For the dual-LLM split that breaks indirect-prompt-injection paths, this capability covers the input-classifier slot; the agent LLM stays separate and never sees raw untrusted input.

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

## Probe

`llama_guard_classify` sends a benign message and asserts the classifier returns `safe`. Run by `agent-scaffold doctor`.

## When to swap it

- **→ `guardrail.llama-guard-local`** — self-hosted vLLM serving the same model.
- **→ `guardrail.openai-moderation`** — OpenAI's hosted moderation endpoint (different taxonomy).
- **→ `guardrail.nemo-guardrails`** — NVIDIA's policy-DSL framework (heavier, more configurable).

## See also

- [`vendored/blueprints/modifiers/guardrails/overview.md`](../../../vendored/blueprints/modifiers/guardrails/overview.md) — pattern-level guidance on dual-LLM safety architecture.
- [`cross-cutting/security-hardening.md`](../../cross-cutting/security-hardening.md) — broader security posture.
