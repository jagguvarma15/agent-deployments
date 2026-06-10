# Zep

> Long-term memory store for `primitives: [memory]` recipes. Used by `memory_store.zep`.

**Signup (cloud)**: https://app.getzep.com — optional. OSS image runs locally.

## Local-first setup

The recipe's compose file brings up Zep alongside Postgres:

```bash
docker compose up -d postgres zep
docker compose logs -f zep | grep -m1 "Server listening"
```

Web admin: http://localhost:8000/admin. The scaffold's `bootstrap_zep` step creates the `zep` Postgres database and the per-tenant user record on first run.

## Rotate the auth secret (before production)

```bash
# In .env.local
ZEP_AUTH_SECRET=$(openssl rand -hex 32)
docker compose restart zep
```

Default `change-me` is fine for local dev only. The compose fragment uses JWT-signed access; if you leave the default, any process on the host can call Zep as any user.

## Wire into your project

Declare `capabilities: [memory_store.zep]` in the recipe. The scaffold wires the Zep client into the recipe's memory primitive — store / recall / summarize all flow through Zep.

Cloud:

```bash
# In .env.local
ZEP_API_URL=https://api.getzep.com
ZEP_API_KEY='zep_...'
```

## Verify

```bash
curl -sS http://localhost:8000/healthz
```

Should print `OK`. From inside the agent project:

```bash
python -c "from zep_python import ZepClient; c=ZepClient('http://localhost:8000'); print(c.health())"
```

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `connection refused 8000` | Zep not up yet | `docker compose logs zep` — wait for "Server listening" |
| `database "zep" does not exist` | bootstrap_zep didn't run | `docker compose exec postgres createdb -U agent zep` |
| `401 unauthorized` (cloud) | Wrong key tier | Cloud keys are project-scoped; recreate per project |
| Summarization quality poor | Default summarizer uses small model | Configure a stronger summarizer via Zep env vars |

## See also

- [`docs/capabilities/memory_store/zep.md`](../capabilities/memory_store/zep.md) — capability definition.
- [`vendored/blueprints/primitives/memory/overview.md`](../../vendored/blueprints/primitives/memory/overview.md) — primitive overview.
