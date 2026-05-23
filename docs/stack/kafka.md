# Stack pick: Kafka

**Choice:** Apache Kafka 3.x in KRaft mode (no ZooKeeper)
**Image:** `bitnami/kafka` or `confluentinc/cp-kafka` for Kafka; `redpanda/redpanda` as a Kafka-API-compatible single-binary alternative
**Used for:** High-throughput event source (>10k events/sec per topic), durable replay (days-to-weeks retention), multi-consumer fan-out across teams

## Why this over alternatives

| Option | Verdict |
|--------|---------|
| Redis Streams | Best fit ≤10k events/sec per stream; covered in `cache-redis.md` and the default for this repo |
| Kafka | 10k–1M+ events/sec/topic; long retention; rich ecosystem (Connect, Streams, Schema Registry); heaviest ops |
| Redpanda | Kafka API-compatible; single binary; lower ops than Kafka; smaller ecosystem |
| AWS SQS / SNS | Managed; lower throughput per queue; no native log replay |
| AWS MSK / Confluent Cloud / Aiven Kafka | Managed Kafka; eliminates broker ops at a price |
| NATS JetStream | Lightweight middle ground; persistent + KV + object store; smaller ecosystem than Kafka |
| RabbitMQ | AMQP push semantics; not log-shaped; harder to replay; weaker fit for stream processing |

For mise: stay on Redis Streams until a single restaurant chain pushes one stream past ~5k events/sec sustained. Migrate to Kafka (or Redpanda) when that happens, or earlier if multi-team fan-out becomes the driver.

## Core concepts

| Concept | What it is |
|---------|------------|
| **Topic** | Append-only log; analogous to a Redis Stream |
| **Partition** | Ordered subset of a topic; in-order processing only within a partition |
| **Partition key** | Determines which partition an event lands in; same key → same partition |
| **Consumer group** | Cooperative consumers; each partition is assigned to exactly one consumer at a time |
| **Offset** | Position in the partition log; the consumer commits its offset to track progress |
| **Replication factor** | Number of brokers storing each partition; 3 in production |
| **Retention** | Time or size limit before old segments are deleted |
| **Compaction** | Per-key "keep latest value" cleanup policy for state-shaped topics |

## Local setup (KRaft, single broker)

```yaml
kafka:
  image: bitnami/kafka:3.7
  ports:
    - "9092:9092"
  environment:
    KAFKA_CFG_NODE_ID: 0
    KAFKA_CFG_PROCESS_ROLES: controller,broker
    KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: "0@kafka:9093"
    KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
    KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
    KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
    ALLOW_PLAINTEXT_LISTENER: "yes"
  volumes:
    - kafka_data:/bitnami/kafka

kafka-ui:
  image: provectuslabs/kafka-ui:latest
  ports: ["8080:8080"]
  environment:
    KAFKA_CLUSTERS_0_NAME: local
    KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
```

Create a topic:

```bash
docker exec -it kafka kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --topic reservations.cancelled \
  --partitions 12 --replication-factor 1
```

## Python integration (aiokafka)

```python
import json
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.structs import TopicPartition, OffsetAndMetadata

# --- Producer ---
producer = AIOKafkaProducer(
    bootstrap_servers="kafka:9092",
    enable_idempotence=True,                          # exactly-once producer semantics
    acks="all",                                       # wait for all in-sync replicas
    value_serializer=lambda v: json.dumps(v).encode(),
    key_serializer=lambda k: k.encode(),
)
await producer.start()

await producer.send_and_wait(
    "reservations.cancelled",
    key="rest-99",                                    # partition key = restaurant_id
    value={"event_id": "evt-abc", "schema_version": 1, "...": "..."},
)

# --- Consumer ---
consumer = AIOKafkaConsumer(
    "reservations.cancelled",
    bootstrap_servers="kafka:9092",
    group_id="rebooker",
    enable_auto_commit=False,                         # commit manually after success
    value_deserializer=lambda v: json.loads(v.decode()),
    auto_offset_reset="earliest",
)
await consumer.start()

async for msg in consumer:
    tp = TopicPartition(msg.topic, msg.partition)
    try:
        await handle_event(msg.value)
        await consumer.commit({tp: OffsetAndMetadata(msg.offset + 1, "")})
    except RetryableError:
        # Do NOT commit — rebalance or seek will redeliver. Sleep + continue, or break to backoff.
        raise
    except PermanentError as e:
        # Send to DLQ, commit to skip the original
        await producer.send_and_wait(
            "reservations.cancelled.dlq",
            value={**msg.value, "_error": str(e)},
        )
        await consumer.commit({tp: OffsetAndMetadata(msg.offset + 1, "")})
```

## TypeScript integration (kafkajs)

```typescript
import { Kafka } from "kafkajs";

const kafka    = new Kafka({ clientId: "rebooker", brokers: ["kafka:9092"] });
const producer = kafka.producer({ idempotent: true });
const consumer = kafka.consumer({ groupId: "rebooker" });

await producer.connect();
await producer.send({
  topic: "reservations.cancelled",
  messages: [{
    key: "rest-99",                                   // restaurant_id
    value: JSON.stringify({ event_id: "evt-abc", schema_version: 1, /* ... */ }),
  }],
});

await consumer.connect();
await consumer.subscribe({ topic: "reservations.cancelled", fromBeginning: false });
await consumer.run({
  autoCommit: false,
  eachMessage: async ({ topic, partition, message }) => {
    try {
      await handleEvent(JSON.parse(message.value!.toString()));
      await consumer.commitOffsets([{
        topic, partition, offset: (Number(message.offset) + 1).toString(),
      }]);
    } catch (err) {
      // route to DLQ + commit to skip, or rethrow to redeliver after rebalance
      throw err;
    }
  },
});
```

## Partition key choice

The partition key dictates the unit of ordering — events with the same key are processed strictly in order; events with different keys can run in parallel.

| Key | Tradeoff |
|-----|----------|
| `restaurant_id` | All events for a restaurant ordered; parallelism = number of distinct restaurants |
| `reservation_id` | Per-reservation ordering; high parallelism; cancellation + rebooking on the same reservation will NOT be ordered relative to each other across reservations of the same restaurant |
| Random / round-robin | Max parallelism; no ordering guarantee |

For mise: `restaurant_id`. Number of partitions caps the per-group consumer parallelism — pick 12–48 per topic for typical workloads. Over-provision rather than under; growing a partition count is painful (it re-keys the partition map for new writes and forces a consumer reshuffle).

## Idempotency

`enable_idempotence=True` (producer) + `acks="all"` + manual offset commits gets you exactly-once write/read semantics in the happy path. Retry-after-crash redeliveries still happen — partition rebalance, consumer crash before commit, producer retry after a transient broker error.

Apply the same idempotency patterns as for Redis Streams. See `cross-cutting/idempotency.md` (PR-D, pending) — `SET idemp:{event_id} ... NX EX` (or the two-phase claim/release variant) keeps the action exactly-once even when delivery is at-least-once.

## DLQ pattern

A parallel topic per source topic, named `<topic>.dlq`. On permanent failure, write to the DLQ and commit the original offset:

```python
await producer.send_and_wait(
    f"{msg.topic}.dlq",
    value={
        **msg.value,
        "_error": str(e),
        "_failed_at": datetime.now(tz=UTC).isoformat(),
        "_source_topic": msg.topic,
        "_source_offset": msg.offset,
    },
)
await consumer.commit({TopicPartition(msg.topic, msg.partition): OffsetAndMetadata(msg.offset + 1, "")})
```

Alert on DLQ insertion rate and DLQ topic depth via the Kafka Lag Exporter → Prometheus pipeline (see `prometheus-grafana.md`).

## Schema management

JSON-blob payloads work at small scale. Past 2–3 services consuming the same topic, formalize with a Schema Registry (Apicurio or Confluent) using Avro / Protobuf / JSON Schema. See `cross-cutting/schema-evolution.md` for the full story (`schema_version` field, change categories, dual-publish migration).

## Operational essentials

- **Replication factor 3** in production — data survives 2 broker failures.
- **`min.insync.replicas=2`** combined with `acks=all` for durable writes; producer fails if fewer than 2 replicas can be written to.
- **Retention** — start at 7 days; tune up if replay is a frequent operation, down if storage is a concern.
- **Compaction** — for state-snapshot topics (key + latest value, e.g. user profile updates): `cleanup.policy=compact`.
- **ACLs from day 1** — per-user / per-topic permissions; SASL/SCRAM or mTLS for client auth.
- **Monitoring** — Kafka Lag Exporter → Prometheus; track consumer lag per group + partition; alert on lag > N seconds or lag growth rate.

## Pitfalls

- **Insufficient partitions** — parallelism cap; you can't add partitions later without disrupting key→partition mapping for existing keys.
- **`acks=1` in production** — data loss on broker crash before replication.
- **Auto-commit enabled** — offsets commit on a timer, possibly before processing finishes; events skipped on crash.
- **Single broker in "production"** — no replication, data loss inevitable when the one node fails.
- **Schema-less JSON without `schema_version`** — producer changes silently break consumers.
- **High consumer lag without alerts** — events accumulate unseen until a SLO is missed.
- **Mixing `acks=all` writes with `min.insync.replicas=1`** — `acks=all` is meaningless when only one replica is required to be in sync.
- **Manual offset commit in the wrong order** — commit before processing succeeds = at-most-once; commit after = at-least-once (correct + paired with idempotency).

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — currently uses Redis Streams; Kafka is the scale-migration target documented in Design decisions.
- [patterns/event-driven.md](../patterns/event-driven.md) — Kafka is one of the listed event-source options.

## Production considerations

- **Managed offerings** (MSK / Confluent Cloud / Aiven) dramatically reduce operational cost — recommended unless you have Kafka expertise on the team.
- **Multi-region replication** — MirrorMaker 2 (open source) or Confluent Replicator (commercial). Cross-region for DR; same-region for low-latency multi-AZ.
- **Schema Registry** — Confluent Schema Registry or Apicurio. Run it HA; lose the registry, lose the ability to deserialize.
- **Network locality** — brokers + producers + consumers in the same AZ for hot paths; cross-AZ for replication topics. Cross-AZ data transfer is the single largest hidden cost in self-managed Kafka.
- **Backup** — `kafka-mirror-maker` to a cold cluster, or snapshot the underlying storage. The default assumption is "replication is the backup" but it does not protect against accidental topic deletion.

## See also

- `cache-redis.md` — Redis Streams for the smaller-scale event source (Tier 1–2).
- `cross-cutting/schema-evolution.md` — `schema_version` discipline and the dual-publish migration playbook.
- `patterns/event-driven.md` — the upstream design pattern.
