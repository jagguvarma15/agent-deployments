# Cross-cutting: Schema evolution

**Concern:** Events outlive consumers. An event written today may be read months later by a consumer that didn't exist when it was written. Schema versioning is non-optional.
**Library:** Pydantic v2 discriminated unions (Py) / Zod discriminated unions (TS); Avro + Confluent / Apicurio Schema Registry at scale.
**Lives in:** Inline below — apply per topic; reinforced by Kafka + Redis Streams stack docs.

## What it provides

- A discipline (`schema_version` field on every event) that works without infrastructure on day 1.
- A change-category table so you know which edits are safe and which are breaking.
- Pydantic / Zod discriminated-union patterns for parsing multiple versions in one consumer.
- Avro / Protobuf + Schema Registry shape for when teams cross.
- A dual-publish migration playbook for the breaking changes that are unavoidable.

## Why this matters

In event-driven systems, producers and consumers deploy independently. The same event topic feeds multiple consumers, often owned by different teams, on different release cadences. Without versioning discipline:

- A new required field breaks every consumer that hasn't redeployed.
- A renamed field becomes invisible to consumers expecting the old name.
- Replay of historical events through evolved code paths corrupts state silently.
- Debugging "why is this consumer not seeing X" takes hours per incident.

The fix costs almost nothing if you adopt it from day 1, and is expensive to retrofit.

## Schema management approaches

| Approach | When to use |
|----------|-------------|
| No schema, raw JSON | Prototype / single-service |
| Documented Pydantic / Zod, no central registry | Early stage; small team; few consumers |
| `schema_version` field + discriminated unions | Mid stage; multiple consumers in one repo |
| JSON Schema in a registry (validation in code) | Cross-team; loose coupling acceptable |
| Avro / Protobuf + Schema Registry (broker-enforced) | Production at scale; multi-team; compatibility policies enforced |
| Cap'n Proto / FlatBuffers | Ultra-low-latency specialized cases |

For mise: start with Pydantic / Zod discriminated unions + `schema_version` on every event. Move to Avro + Schema Registry once 3+ services consume the same topic.

## The `schema_version` discipline

Every event payload includes a top-level `schema_version: int` (or `"1.2.0"` string if you want semantic versioning). Consumers branch on it before any other field access:

```python
match event["schema_version"]:
    case 1:
        return parse_v1(event)
    case 2:
        return parse_v2(event)
    case _:
        log.warning("unknown_schema_version", version=event["schema_version"])
        return None  # skip; alert if these accumulate
```

Producers bump the version on **every** change. Consumers decide what to do with each version — parse, ignore, upgrade-in-memory, or skip.

## Change categories

| Change | Compatibility | Notes |
|--------|--------------|-------|
| Add **optional** field | Backward + Forward compatible | Safe — old consumers ignore, new consumers see default |
| Add **required** field | Backward-incompatible | Old producers don't write it; new consumers crash |
| Remove a field | Forward-incompatible | New consumers don't have it; old consumers may expect it |
| Rename a field | Both incompatible | Effectively remove + add. Use add-new + deprecate-old. |
| Change a field's type | Backward-incompatible | Never reuse a name. Add a new versioned field. |
| Change semantics of an existing field | Backward-incompatible | Bump version + deprecation note in the doc |

**Rule of thumb:** every change is either "add a new optional field" or "bump major version and dual-publish." Never edit a field in place.

## Pydantic discriminated unions

For Python consumers that need to read multiple versions in one process:

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field

class CancellationEventV1(BaseModel):
    schema_version: Literal[1]
    event_id: str
    restaurant_id: str
    reservation_id: str
    party_size: int
    reservation_time: datetime
    cancelled_at: datetime
    reason: str
    trace_id: str

class CancellationEventV2(BaseModel):
    schema_version: Literal[2]
    event_id: str
    restaurant_id: str
    reservation_id: str
    party_size: int
    reservation_time: datetime
    cancelled_at: datetime
    reason: str
    trace_id: str
    customer_id: str | None = None          # new optional in v2
    channel_preference: str | None = None   # new optional in v2

CancellationEvent = Annotated[
    Union[CancellationEventV1, CancellationEventV2],
    Field(discriminator="schema_version"),
]

# Usage
event = TypeAdapter(CancellationEvent).validate_python(payload)
```

The discriminator dispatch is O(1) and the type checker knows the right shape inside each branch. Add `V3` when needed; old versions keep working.

## Zod discriminated unions

```typescript
import { z } from "zod";

const CancellationEventV1 = z.object({
  schema_version: z.literal(1),
  event_id: z.string(),
  restaurant_id: z.string(),
  reservation_id: z.string(),
  party_size: z.number().int(),
  reservation_time: z.string().datetime(),
  cancelled_at: z.string().datetime(),
  reason: z.string(),
  trace_id: z.string(),
});

const CancellationEventV2 = CancellationEventV1.extend({
  schema_version: z.literal(2),
  customer_id: z.string().nullable().optional(),
  channel_preference: z.string().nullable().optional(),
});

export const CancellationEvent = z.discriminatedUnion("schema_version", [
  CancellationEventV1,
  CancellationEventV2,
]);

export type CancellationEvent = z.infer<typeof CancellationEvent>;
```

## Avro + Schema Registry (cross-team scale)

When producers and consumers belong to different teams or repos, formalize via a registry:

- Schemas live in the registry, versioned.
- Producers register a schema before writing; the broker stores the schema id alongside the payload (5 bytes overhead per message in Confluent's wire format).
- Consumers fetch the schema by id and deserialize.
- The registry enforces a **compatibility policy** at registration:
  - `BACKWARD` — new schema can read data written with old schema (consumer-first rollout).
  - `FORWARD` — old schema can read data written with new schema (producer-first rollout).
  - `FULL` — both directions (the strictest, the safest).
  - `NONE` — anything goes (don't).

Avro schema for our `CancellationEvent`:

```json
{
  "type": "record",
  "name": "CancellationEvent",
  "namespace": "mise.reservations",
  "fields": [
    {"name": "event_id",          "type": "string"},
    {"name": "schema_version",    "type": "int", "default": 2},
    {"name": "restaurant_id",     "type": "string"},
    {"name": "reservation_id",    "type": "string"},
    {"name": "party_size",        "type": "int"},
    {"name": "reservation_time",  "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "cancelled_at",      "type": {"type": "long", "logicalType": "timestamp-millis"}},
    {"name": "reason",            "type": {"type": "enum", "name": "CancellationReason",
                                            "symbols": ["customer_cancelled", "no_show",
                                                        "restaurant_cancelled", "weather", "unknown"]}},
    {"name": "customer_id",       "type": ["null", "string"], "default": null},
    {"name": "trace_id",          "type": "string"},
    {"name": "channel_preference","type": ["null", "string"], "default": null}
  ]
}
```

Adding a new field with a `default` is a `BACKWARD`-compatible change — the registry accepts it; old consumers reading new events ignore the field; new consumers reading old events see the default.

## Migration playbook (breaking changes)

When you must make a breaking change (renamed field, changed type, restructured payload), use **dual-publish**:

1. **Phase 1 — dual-publish.** Producer writes both v1 and v2 events to the topic (different `schema_version`). Old consumers ignore v2, read v1 as usual. New consumer reads v2, ignores v1.
2. **Phase 2 — migrate consumers.** Switch each consumer to v2 one at a time, validated in staging first. Monitor for parse errors.
3. **Phase 3 — single-publish.** Producer stops writing v1. Any v1 events still in the topic (within retention) are processed by v1-aware consumers or skipped.
4. **Phase 4 — cleanup.** Once retention has aged out the last v1 event, remove v1 code paths.

Phase boundaries take days or weeks — don't shortcut. The cost of doing it right once is much less than the cost of doing it wrong every time.

## Test patterns

- **Version-roundtrip test** — write v1 with the v1 schema, read with the v2 (discriminated-union-aware) consumer; assert correct parsing.
- **Forward-incompatibility detection** — write v2, attempt to read with a v1-only consumer; assert the v1 consumer falls through to the "unknown version" branch (and doesn't crash).
- **Schema-registry CI check** — proposed schema changes run through a `BACKWARD` (or `FULL`) compatibility check against the latest registered version before merge.
- **Field-removal regression** — golden v1 payloads in a fixtures directory; every consumer must continue parsing them across releases.

## Pitfalls

- **Schema change without version bump** — silent corruption; the worst class of bug.
- **Removing a field "because no one uses it"** — somebody does.
- **Renaming a field as if it were a no-op** — it's an add-new + remove-old in disguise, treat it as breaking.
- **Adding a required field without dual-publish** — producer-consumer mismatch the moment anyone deploys.
- **Schema registry without a compatibility policy** — drifts into chaos; default to `BACKWARD` or `FULL`.
- **Mixed `schema_version` shapes across services** (some int, some semver string) — coordination nightmare; pick one in this doc and enforce.
- **Deep optionality** (every field optional "just in case") — push the validation to the consumer, where it costs more to test.

## Where used in repo

- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `CancellationEvent` carries `schema_version: int`; consumer parses via Pydantic discriminated union.
- [stack/kafka.md](../stack/kafka.md) — at scale, register schemas in Confluent / Apicurio rather than inlining versioned classes.

## See also

- `stack/kafka.md` — Kafka as the scale event source where Schema Registry kicks in.
- `stack/cache-redis.md` — Redis Streams as the small-scale event source; `schema_version` discipline applies equally.
