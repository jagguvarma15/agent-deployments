# Langfuse

> Open-source LLM observability. Captures traces, generations, scores, and prompts. Optional but recommended once you have more than one user.

**Signup**: https://cloud.langfuse.com (or self-host)

## Quick start (hosted)

1. Sign up at https://cloud.langfuse.com
2. Create a **project** (free tier: 50k events/month)
3. Settings → API Keys → copy the **Public Key** and **Secret Key**

## Self-host (Docker)

```bash
git clone https://github.com/langfuse/langfuse
cd langfuse
docker compose up -d
# UI on http://localhost:3000; create a user, then a project, then keys.
```

Langfuse needs Postgres + ClickHouse + MinIO under the hood; the bundled compose handles all three. See [`docs/stack/tracing-langfuse.md`](../stack/tracing-langfuse.md) for the full topology and config knobs.

## Verify

```bash
curl -s "$LANGFUSE_HOST/api/public/health"   # → {"status":"OK"}
```

After your first agent run, the trace shows up at `$LANGFUSE_HOST/project/<id>/traces` within a few seconds.

## Wire into your project

Set in `.env.local`:

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

For self-host: `LANGFUSE_HOST=http://localhost:3000`.

Most recipes register the Langfuse callback automatically when these vars are set. No code changes needed.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` from `/api/public/health` | Key / host mismatch | Re-check that `LANGFUSE_PUBLIC_KEY` matches `LANGFUSE_HOST` |
| No traces visible in UI | Callback not registered | Confirm the LangChain / framework callback handler is attached at agent startup |
| `Network unreachable` on self-host | Compose stack didn't finish starting | `docker compose ps`; wait for `langfuse-web` to be `healthy` |
| Traces missing tool-call detail | Older SDK version | Pin `langfuse>=2.40` |

## See also

- [`docs/stack/tracing-langfuse.md`](../stack/tracing-langfuse.md) — model-level cost tracking, scoring, prompt management
- [`docs/cross-cutting/observability.md`](../cross-cutting/observability.md) — wiring conventions
- [`docs/cross-cutting/cost-tracking.md`](../cross-cutting/cost-tracking.md) — per-run cost rollups
