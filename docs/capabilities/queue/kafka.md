---
id: queue.kafka
kind: queue
provides: [event_source, durable_log, replay]
env_vars: [KAFKA_BOOTSTRAP_SERVERS, KAFKA_CLIENT_ID]
docker:
  service: kafka
  image: bitnami/kafka:3.7
  ports: ["9092:9092"]
  volumes: ["kafka_data:/bitnami/kafka"]
  environment:
    KAFKA_CFG_NODE_ID: "0"
    KAFKA_CFG_PROCESS_ROLES: "controller,broker"
    KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: "0@kafka:9093"
    KAFKA_CFG_LISTENERS: "PLAINTEXT://:9092,CONTROLLER://:9093"
    KAFKA_CFG_ADVERTISED_LISTENERS: "PLAINTEXT://kafka:9092"
    KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT"
    KAFKA_CFG_CONTROLLER_LISTENER_NAMES: "CONTROLLER"
    ALLOW_PLAINTEXT_LISTENER: "yes"
probe: kafka_topic_list
bootstrap_step: bootstrap_kafka
emit_files: []
docs: |
  Apache Kafka 3.x in KRaft mode (no ZooKeeper). Bootstrap step creates the
  topics declared by the recipe via `KafkaAdminClient`. For lower throughput
  (≤10k events/sec) prefer `queue.redis-streams`.
---

# Capability: queue.kafka

> Deep reference: [`stack/kafka.md`](../../stack/kafka.md). This page is the provisioning contract.

**Used for:** high-throughput event source (>10k events/sec per topic), durable replay (days-to-weeks retention), multi-consumer fan-out.

## Why pick this

When the event-source throughput or retention requirement outgrows Redis Streams. Single-binary alternative: switch the `image:` to `redpanda/redpanda` — same capability id and bootstrap step, smaller ops footprint, slightly smaller ecosystem.

## Local setup

The KRaft fragment above runs Kafka without ZooKeeper. Single broker, single port — fine for local dev, not production. The probe (`kafka_topic_list`) hits `KafkaAdminClient.list_topics()` to confirm the broker accepts admin connections.

## Bootstrap (post docker_up)

`bootstrap_kafka` reads the recipe frontmatter `kafka_topics:` block (or per-capability defaults) and idempotently creates each topic:

```python
from kafka.admin import KafkaAdminClient, NewTopic
admin = KafkaAdminClient(bootstrap_servers=os.environ["KAFKA_BOOTSTRAP_SERVERS"])
existing = set(admin.list_topics())
to_create = [
    NewTopic(name=t["name"], num_partitions=t["partitions"], replication_factor=1)
    for t in topics if t["name"] not in existing
]
if to_create:
    admin.create_topics(to_create, validate_only=False)
```

Optional dep in the generated project: `aiokafka` (Python) or `kafkajs` (TypeScript). `kafka-python` is used by the bootstrap step only.

## Env vars

| Var | Default | Purpose |
|-----|---------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:9092` (in compose) / `localhost:9092` (from host) | Broker list, comma-separated |
| `KAFKA_CLIENT_ID` | `<project>-agent` | Producer/consumer client id for monitoring |

## Cloud / production

- **Managed** — Confluent Cloud, AWS MSK, Aiven Kafka. Set `KAFKA_BOOTSTRAP_SERVERS` to the broker list + SASL credentials.
- **Self-hosted** — replication factor 3, `min.insync.replicas=2`, ACLs from day one, monitoring via Kafka Lag Exporter → Prometheus.

## When to swap it

- **→ `queue.redis-streams`** if sustained throughput is ≤5k events/sec/stream and hours-of-retention is enough. Less infra, same agent shape.

## See also

- `stack/kafka.md` — full reference including partition keys, idempotency, DLQ patterns
- `cross-cutting/schema-evolution.md` — schema_version discipline for cross-team topics
- `cross-cutting/dlq-operations.md` — DLQ runbook
