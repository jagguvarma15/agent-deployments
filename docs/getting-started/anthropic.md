# Anthropic API

> The LLM provider every recipe in this repo targets. You need an API key before `agent-scaffold new` will call out.

**Signup**: https://console.anthropic.com

## Create a key

1. Open the console at https://console.anthropic.com
2. Pick the right **workspace** at the top — a key created in your personal workspace will fail with 401 against a team workspace and vice versa.
3. Settings → API Keys → **Create Key**. Name it after the machine or env that will use it (`laptop-2026`, `ci-prod`, etc.).
4. Copy the key — it starts with `sk-ant-` and is shown **once**.

## Wire into your project

Pick one of:

```bash
# Shell env — fine for one-off runs; ends up in shell history
export ANTHROPIC_API_KEY='sk-ant-...'

# Recommended: store in OS keychain via agent-scaffold
agent-scaffold auth login

# CI: pipe in from a secret manager
echo "$ANTHROPIC_KEY_FROM_VAULT" | agent-scaffold auth setup-token ci-prod --stdin
```

`agent-scaffold` resolves keys in this order: `ANTHROPIC_API_KEY` env → keyring → mode-0600 credentials file.

## Verify

```bash
python -c "import anthropic; print(len(list(anthropic.Anthropic().models.list().data)), 'models visible')"
```

Or via the CLI once a key is stored:

```bash
agent-scaffold auth status
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` | Key revoked, or wrong workspace | Recreate the key in the workspace your usage tier covers |
| `429 Too Many Requests` | Hit the free-tier rate limit, or no paid tier yet | Add a payment method on the console; raise tier |
| `SSLCertVerificationError` | Corporate root CA not in your trust store | `export SSL_CERT_FILE=$(python -m certifi)` |
| `Connection error: ... timed out` | Outbound firewall blocks `api.anthropic.com` | Allowlist the host; check VPN routing |

## See also

- [`docs/stack/llm-claude.md`](../stack/llm-claude.md) — model picks, pricing, prompt caching
- [`docs/cross-cutting/cost-tracking.md`](../cross-cutting/cost-tracking.md) — measuring spend per run
