---
id: guardrail.injection-classifier
kind: guardrail
implements:
  port: guardrail
  interface_version: "1.0"
layer: agent
provides: [input_classification, prompt_injection_detection]
env_vars: [GUARDRAIL_CLASSIFIER_URL]
hosting: [docker]
docker:
  service: guardrail-classifier
  image: ghcr.io/huggingface/text-embeddings-inference:cpu-1.6
  # TEI's CPU images publish amd64 only (no arm64 manifest through cpu-latest).
  # Pinning the platform runs the service under emulation on Apple Silicon
  # instead of hard-failing the pull; on amd64 hosts it matches native and is
  # a no-op. Verified emulated on an M-series host: healthy, ~86ms/inference.
  platform: linux/amd64
  environment:
    MODEL_ID: protectai/deberta-v3-base-prompt-injection-v2
  ports: ["8081:80"]
  volumes: ["guardrail_model_data:/data"]
  healthcheck:
    test: ["CMD-SHELL", "wget -qO- http://localhost:80/health || exit 1"]
    interval: 10s
    timeout: 5s
    retries: 10
probe: null
bootstrap_step: null
provisioning_time: ~30s first run (model download), instant after
cost_tier: free
est_tokens: 550
card:
  name: Prompt-injection classifier (local)
  description: "ProtectAI's DeBERTa-v3 prompt-injection classifier served locally by Text Embeddings Inference — input-side injection and jailbreak-attempt detection with no API key."
  capabilities_provided: [prompt_injection_detection, input_classification]
  required_credentials: []
emit_files: []
docs: |
  A local prompt-injection classifier wrapping the agent's input surface:
  ProtectAI's deberta-v3-base-prompt-injection-v2 served by Text Embeddings
  Inference (the same serving image as embedding.local-bge). The generated
  project POSTs user input to GUARDRAIL_CLASSIFIER_URL/predict (default
  http://localhost:8081) and receives label + score; INJECTION at or above
  the confidence threshold (default 0.9) denies the request before it
  reaches the LLM. Complements guardrail.llama-guard rather than replacing
  it: llama-guard classifies content safety on both input and output, this
  classifier detects injection and jailbreak attempts on input — production
  stacks commonly run both. No API key; the model downloads on first
  docker_up.
tags: [guardrail, prompt-injection, security, local, self-hosted]
when_to_load: "recipe declares guardrail.injection-classifier"
---

# Capability: guardrail.injection-classifier

> Vendor: https://huggingface.co/protectai/deberta-v3-base-prompt-injection-v2 · Serving: https://github.com/huggingface/text-embeddings-inference

**Used for:** Detecting prompt-injection and jailbreak attempts in user input before it reaches the LLM — the input-side security complement to `guardrail.llama-guard`'s content-safety classification.

## Relationship to guardrail.llama-guard

The two guardrails answer different questions and compose:

| | llama-guard | injection-classifier |
|---|---|---|
| Question | Is this content harmful? | Is this input trying to subvert the agent? |
| Surfaces | Input and output | Input only |
| Runs | Hosted (Together AI, per-call) | Local container (free) |
| Credential | `TOGETHER_API_KEY` | None |

Production stacks commonly run both; either stands alone.

## Wiring

```yaml
# In a recipe's frontmatter:
guardrails: [guardrail.injection-classifier]
```

The scaffold emits the input hook in the generated project:

- `pre_llm_call(messages) → allow | deny(reason)` — the latest user message is
  classified; a deny short-circuits the agent loop and returns a structured
  error (HTTP 403 with `safety.category: prompt_injection` in the body).

## Classification contract

TEI serves the model's sequence-classification head at `/predict`:

```python
import httpx

async def classify(text: str) -> tuple[bool, float]:
    resp = await httpx.AsyncClient().post(
        f"{os.environ.get('GUARDRAIL_CLASSIFIER_URL', 'http://localhost:8081')}/predict",
        json={"inputs": text},
    )
    resp.raise_for_status()
    top = resp.json()[0]
    is_injection = top["label"] == "INJECTION" and top["score"] >= 0.9
    return (not is_injection, top["score"])
```

The 0.9 threshold is the shipped default — tune per recipe; lower catches
more at the cost of false positives on unusual-but-legitimate phrasing.

## Fail-open vs fail-closed

The classifier is local, so unavailability means the container is down, not a
network blip. Default **fail-closed** (a classification error denies the
request) for agents with tool access or side effects; fail-open is defensible
only for read-only chat agents where availability outranks the injection
risk. Either way, log the failure — a silently skipped guardrail is the worst
of both. This mirrors the guidance in the blueprints guardrails modifier's
integration doc.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `GUARDRAIL_CLASSIFIER_URL` | `http://localhost:8081` | TEI classification endpoint |

Configuration, not a credential — no keyring entry, no prompt.
