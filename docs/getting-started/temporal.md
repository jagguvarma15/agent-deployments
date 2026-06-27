# Temporal

> Durable execution for long-horizon agent tasks. Used by `durable.temporal`.

**Signup (cloud)**: https://temporal.io/cloud — optional. The OSS image works locally without an account.

## Local-first setup

The recipe's compose file (via `durable.temporal`) brings up Temporal alongside Postgres in one command:

```bash
docker compose up -d postgres temporal
docker compose logs -f temporal | grep -m1 "TemporalServer started"
```

Web UI: http://localhost:8233. The compose fragment auto-creates Temporal's keyspaces on first boot.

## Create a namespace

The scaffold's `bootstrap_temporal` step does this automatically. Manual equivalent:

```bash
docker compose exec temporal tctl --address temporal:7233 \
  namespace register default \
  --retention 1
```

Idempotent — re-running is a no-op.

## Wire into your project

```bash
# In .env.local (already populated by scaffold's bootstrap):
TEMPORAL_HOST=temporal:7233
TEMPORAL_NAMESPACE=default
```

For Temporal Cloud:

```bash
TEMPORAL_HOST=<your-namespace>.tmprl.cloud:7233
TEMPORAL_NAMESPACE=<your-namespace>
# Plus mTLS certs — provide via env-var paths or SDK config
```

## Verify

```bash
docker compose exec temporal tctl --address temporal:7233 cluster health
```

Should print `OK`. Web UI at http://localhost:8233 should list `default` under Namespaces.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Namespace default not found` | Bootstrap step didn't run | `bootstrap_temporal` manually (see above) |
| Worker pod crashes on start | `TEMPORAL_HOST` unreachable | Check compose service name + network |
| `cluster unavailable` | Postgres for Temporal not ready | `docker compose logs postgres` — wait for `ready to accept connections` |
| mTLS handshake fails (cloud) | Cert path / format mismatch | Paths must be PEM; both client cert + key set |

## See also

- [`docs/capabilities/durable/temporal.md`](../capabilities/durable/temporal.md) — capability definition.
- [`patterns/long_horizon/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/patterns/long_horizon/overview.md) — pattern that motivates this.
