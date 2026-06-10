# Llama Guard 3 (via Together AI)

> Safety classifier for `guardrails: [guardrail.llama-guard]`. Hosted via Together AI by default; self-hostable.

**Signup**: https://api.together.ai

## Create a key

1. Sign in at https://api.together.ai
2. **Settings** → **API Keys** → **Create Key**.
3. Copy the key (shown once). Free tier ships ~$25 in credits; Llama Guard 3 8B costs cents per million tokens.

## Wire into your project

```bash
# Recommended: store in OS keychain via agent-scaffold
agent-scaffold auth login --provider together

# Or shell env:
export TOGETHER_API_KEY='...'
```

Declare `guardrails: [guardrail.llama-guard]` in the recipe's frontmatter. The scaffold emits `pre_llm_call` and `post_llm_call` hooks; denials short-circuit the agent loop with HTTP 403 + the violation category.

## Verify

```bash
curl -sS -X POST https://api.together.xyz/v1/chat/completions \
  -H "Authorization: Bearer $TOGETHER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"meta-llama/Llama-Guard-3-8B","messages":[{"role":"user","content":"hello"}]}' \
  | head -30
```

Should return a completion whose first line is `safe`.

## Self-host alternative

For data-residency requirements, swap to `guardrail.llama-guard-local` (planned). Runs the same model under vLLM with a single A10 / L4 GPU.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401` | Key revoked / typo | Recreate at https://api.together.ai |
| `404 model not found` | Together AI rotated the model id | Check current id at https://api.together.ai/models; update the capability frontmatter |
| Classifier denies benign input | False positive on Llama Guard's taxonomy | Switch `guardrail.openai-moderation` for a different taxonomy |
| Latency 800ms+ per call | Cold start | Together caches warm pods; latency drops after a few calls |

## See also

- [`docs/capabilities/guardrail/llama-guard.md`](../capabilities/guardrail/llama-guard.md) — capability definition.
- [`vendored/blueprints/modifiers/guardrails/overview.md`](../../vendored/blueprints/modifiers/guardrails/overview.md) — pattern-level guidance.
