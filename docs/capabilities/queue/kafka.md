---
id: queue.kafka
kind: queue
implements:
  port: queue
  interface_version: "1.0"
layer: infrastructure
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
  healthcheck:
    test: ["CMD-SHELL", "kafka-topics.sh --bootstrap-server localhost:9092 --list || exit 1"]
    interval: 10s
    timeout: 10s
    retries: 5
    start_period: 30s
probe: kafka_topic_list
bootstrap_step: bootstrap_kafka
provisioning_time: ~30s
cost_tier: free
est_tokens: 950
card:
  name: Apache Kafka
  description: "Kafka 3.x in KRaft mode (no ZooKeeper) for high-throughput durable event log."
  capabilities_provided: [event_source, durable_log, replay, consumer_groups]
  required_credentials: []
emit_files: []
docs: |
  Apache Kafka 3.x in KRaft mode. Bootstrap step creates the topics declared
  by the recipe via `KafkaAdminClient`. Pair with `queue.redis-streams`
  instead for ≤10k events/sec workloads.
tags: [queue, high-throughput, durable]
when_to_load: "recipe declares queue.kafka"
---

# Capability: queue.kafka

> Deep reference: [`stack/kafka.md`](../../stack/kafka.md). This page is the provisioning contract.

**Used for:** high-throughput event source (>10k events/sec per topic), durable replay (days-to-weeks retention), multi-consumer fan-out.

## Local setup

The KRaft fragment above runs Kafka without ZooKeeper. Single broker, single port — fine for local dev. The probe (`kafka_topic_list`) hits `KafkaAdminClient.list_topics()` to confirm the broker accepts admin connections.

## Bootstrap (post docker_up)

`bootstrap_kafka` reads the recipe's [`bootstrap_config.kafka_topics`](../../recipes/SCHEMA.md#bootstrap_configkafka_topics) block and idempotently creates each topic:

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

## Client integration

**Python (aiokafka):**

```python
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
producer = AIOKafkaProducer(bootstrap_servers=os.environ["KAFKA_BOOTSTRAP_SERVERS"])
await producer.start()
await producer.send_and_wait("events.in", json.dumps({"id": 1}).encode())

consumer = AIOKafkaConsumer(
    "events.in",
    bootstrap_servers=os.environ["KAFKA_BOOTSTRAP_SERVERS"],
    group_id="agent-worker",
)
await consumer.start()
async for msg in consumer:
    process(json.loads(msg.value))
```

**TypeScript (kafkajs):**

```ts
import { Kafka } from "kafkajs";
const kafka = new Kafka({
  clientId: process.env.KAFKA_CLIENT_ID!,
  brokers: process.env.KAFKA_BOOTSTRAP_SERVERS!.split(","),
});

const producer = kafka.producer();
await producer.connect();
await producer.send({ topic: "events.in", messages: [{ value: JSON.stringify({ id: 1 }) }] });

const consumer = kafka.consumer({ groupId: "agent-worker" });
await consumer.subscribe({ topic: "events.in" });
await consumer.run({ eachMessage: async ({ message }) => process(JSON.parse(message.value!.toString())) });
```

## Cloud / production

- **Managed** — Confluent Cloud, AWS MSK, Aiven Kafka. Set `KAFKA_BOOTSTRAP_SERVERS` to the broker list + SASL credentials.
- **Self-hosted** — replication factor 3, `min.insync.replicas=2`, ACLs from day one, monitoring via Kafka Lag Exporter → Prometheus.

## Troubleshoot

| Symptom | Cause | Fix |
|---------|-------|-----|
| `NoBrokersAvailable` | Broker not advertising the host the client can reach | Confirm `KAFKA_CFG_ADVERTISED_LISTENERS` matches the network the client uses (compose: `kafka:9092`; host: `localhost:9092`) |
| Topics never appear after bootstrap | `bootstrap_kafka` ran before broker was ready | Re-run `bootstrap_kafka`; raise broker healthcheck `retries:` for slow boots |
| `UnknownTopicOrPartitionError` | Topic created in the wrong cluster | Verify producer + consumer point at the same bootstrap servers |
| Slow consumer lag | Single broker, single partition | Add partitions (>=3) on topic recreate; scale consumers within the group |

## See also

- [`stack/kafka.md`](../../stack/kafka.md) — full reference: partition keys, idempotency, DLQ patterns
- [`cross-cutting/schema-evolution.md`](../../cross-cutting/schema-evolution.md) — schema_version discipline for cross-team topics
- [`cross-cutting/dlq-operations.md`](../../cross-cutting/dlq-operations.md) — DLQ runbook
- [`playbook/troubleshoot-local-bringup.md`](../../playbook/troubleshoot-local-bringup.md) — cross-capability diagnostics
