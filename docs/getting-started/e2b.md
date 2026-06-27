# E2B

> Hosted sandbox for running LLM-emitted code in an isolated container. Used by `sandbox.e2b`.

**Signup**: https://e2b.dev

## Create a key

1. Sign in at https://e2b.dev with GitHub or Google.
2. **API Keys** → **Create new key**. Name it after the env (`laptop-2026`, `ci-prod`).
3. Copy the key — starts with `e2b_` and is shown **once**.
4. Free tier ships ~100 hours/month of sandbox time; paid tiers raise concurrency + per-session timeout.

## Wire into your project

```bash
# Recommended: store in OS keychain via agent-scaffold
agent-scaffold auth login --provider e2b

# Or shell env:
export E2B_API_KEY='e2b_...'
```

Declare `sandbox: sandbox.e2b` in the recipe's frontmatter. The scaffold emits a `run_code(language, source)` tool the agent can call; results stream back as observation events.

## Verify

```bash
python -c "from e2b_code_interpreter import Sandbox; s=Sandbox(); print(s.run_code('print(2+2)').logs.stdout[0])"
```

Should print `4`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401` | Key revoked / typo | Recreate in dashboard |
| `429` / concurrency limit | Free tier saturation | Wait, or upgrade tier |
| Session timeout mid-run | Default 5-min cap | Raise via `Sandbox(timeout=…)` or upgrade tier |
| Local imports fail in sandbox | Sandbox is clean Python — install via `s.run_code("!pip install foo")` |

## See also

- [`docs/capabilities/sandbox/e2b.md`](../capabilities/sandbox/e2b.md) — capability definition.
- [`foundations/sandboxed-execution.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/sandboxed-execution.md) — execution-isolation guidance.
