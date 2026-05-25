# Kafka

> Distributed event log. Use for >10k events/sec, durable replay across days, or multi-team fan-out. For smaller volumes, Redis Streams (see `redis.md`) is simpler.

**Signup**: not required for local Docker; hosted options below.

## Quick install (Redpanda — single binary, Kafka API-compatible)

Redpanda is the lowest-friction option for local dev: one container, no ZooKeeper, no JVM:

```bash
docker run -d --name redpanda -p 9092:9092 \
  redpandadata/redpanda:latest \
  redpanda start --smp 1 --memory 512M --overprovisioned \
    --kafka-addr internal://0.0.0.0:9092 \
    --advertise-kafka-addr internal://localhost:9092
```

Wait ~15 seconds for the broker to become reachable.

## Alternative: full Apache Kafka

If you need the official Kafka image (Schema Registry, Connect, Streams):

```bash
docker run -d --name kafka -p 9092:9092 \
  -e KAFKA_CFG_NODE_ID=0 \
  -e KAFKA_CFG_PROCESS_ROLES=controller,broker \
  -e KAFKA_CFG_CONTROLLER_QUORUM_VOTERS="0@localhost:9093" \
  -e KAFKA_CFG_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 \
  -e KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092 \
  -e KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e ALLOW_PLAINTEXT_LISTENER=yes \
  bitnami/kafka:3.7
```

## Hosted alternatives

| Provider | Free tier | Quickstart |
|----------|-----------|------------|
| Confluent Cloud | $400 trial credit | https://www.confluent.io/get-started/ |
| Redpanda Cloud | 14-day trial | https://redpanda.com/redpanda-cloud |
| Upstash Kafka | 10k messages/day | https://upstash.com/docs/kafka/overall/getstarted |
| AWS MSK | none (paid) | regional VPC setup |

## Verify

```bash
nc -z localhost 9092 && echo "broker reachable"
# Or with rpk (ships in the Redpanda container):
docker exec redpanda rpk cluster info
```

## Wire into your project

Set in `.env.local`:

```
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

For Confluent / hosted with SASL: also set `KAFKA_SECURITY_PROTOCOL=SASL_SSL`, `KAFKA_SASL_MECHANISM=PLAIN`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused` immediately after `docker run` | Broker still starting | Wait 10–20 seconds; retry `nc -z localhost 9092` |
| `UnknownTopicOrPartitionException` | Topic auto-create disabled | Create the topic explicitly: `docker exec redpanda rpk topic create reservations` |
| Consumer reads nothing | Wrong consumer group offset (`latest` vs `earliest`) | Pass `auto_offset_reset='earliest'` for the first run |
| `LEADER_NOT_AVAILABLE` on `localhost` connect | `advertised.listeners` mismatch | Make sure the advertised host matches the host the client uses |

## See also

- [`docs/stack/kafka.md`](../stack/kafka.md) — partition design, retention, schema registry, KRaft tuning
- [`docs/cross-cutting/schema-evolution.md`](../cross-cutting/schema-evolution.md) — evolving event payloads
- [`docs/cross-cutting/backpressure.md`](../cross-cutting/backpressure.md) — handling consumer lag
