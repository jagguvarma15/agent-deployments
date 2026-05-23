# Cross-cutting: Validation strategy

**Concern:** Validate at every trust boundary with typed models. Treat anything you didn't construct yourself — user input, event payload, tool return value, LLM output, config — as untrusted until parsed into a typed object.
**Library:** Pydantic v2 (Py) / Zod (TS); per-LLM-SDK structured-output binding.
**Lives in:** Inline below — applied at every recipe's boundary layer.

## What it provides

- A clear list of trust boundaries and which validation owns each one.
- Pydantic v2 + Zod patterns: strict mode, computed fields, cross-field validators, discriminated unions, settings validators.
- LLM output validation — the boundary most teams skip and most regret skipping.
- Error-response shape that's safe to return to clients.
- An error-handling matrix that says what to do when validation fails at each boundary.

## Trust boundaries

A boundary is anywhere data crosses from less-trusted to more-trusted code. Boundary validation is mandatory; internal validation is an asset against bug-spread.

| Boundary | Source | Owns validation |
|----------|--------|-----------------|
| HTTP request body | External callers | Request DTO with `extra="forbid"` |
| HTTP query params | External callers | Query model |
| Event payload | Producer service | Event DTO (versioned — see `schema-evolution.md`) |
| Tool return value | LLM-invoked external tools | Tool-response model |
| **LLM structured output** | **LLM (untrusted!)** | **Pydantic / Zod schema bound to the tool input** |
| Database row | Storage layer | Domain model |
| Config / env vars | Operator | Settings model with `model_validator` |
| Inter-service RPC | Another team's service | RPC contract model |

Data passing between modules in the same service is generally trusted; you can validate there as a safety asset, but it's not a requirement.

## Pydantic v2 patterns (Python)

### Strict mode at boundaries

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class CancellationEvent(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: str
    party_size: int
    cancelled_at: datetime
    reservation_time: datetime
```

`strict=True` disables coercion — `"4"` will not become `4`. `extra="forbid"` rejects unknown fields outright instead of silently dropping them. Use both at boundaries. Relax `strict` only for internal models when you know coercion is intentional.

### Computed fields for derived state

```python
from pydantic import BaseModel, computed_field

class Event(BaseModel):
    cancelled_at: datetime
    reservation_time: datetime

    @computed_field
    @property
    def minutes_until_reservation(self) -> int:
        return int((self.reservation_time - self.cancelled_at).total_seconds() // 60)
```

Computed fields are derived from validated input, not received from outside — they're always trustworthy.

### Cross-field validators

```python
from pydantic import model_validator

class Event(BaseModel):
    cancelled_at: datetime
    reservation_time: datetime

    @model_validator(mode="after")
    def check_window(self) -> "Event":
        if self.cancelled_at >= self.reservation_time:
            raise ValueError("cancelled_at must precede reservation_time")
        return self
```

Use `mode="after"` to validate against the typed values; `mode="before"` operates on raw input and is rarely what you want.

### Discriminated unions for polymorphic payloads

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, TypeAdapter

class FillFromWaitlist(BaseModel):
    action: Literal["fill_from_waitlist"]
    target_customer_id: str

class OfferAltTime(BaseModel):
    action: Literal["offer_alt_time"]
    slot_iso: datetime

class NoAction(BaseModel):
    action: Literal["no_action"]
    reason: str

Decision = Annotated[
    Union[FillFromWaitlist, OfferAltTime, NoAction],
    Field(discriminator="action"),
]

# At the boundary:
decision = TypeAdapter(Decision).validate_python(raw)
```

The discriminator dispatches in O(1); the type checker narrows correctly inside each branch.

### Reject defaults in production (settings)

```python
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_env: str = "development"
    jwt_secret: str = ""

    @model_validator(mode="after")
    def no_defaults_in_prod(self) -> "Settings":
        if self.app_env == "production" and self.jwt_secret in {"", "change-me", "dev-secret"}:
            raise ValueError("JWT_SECRET cannot be empty/default in production")
        return self
```

Boot-time validation. If it fails, the process exits before it serves a single request. See `stack/secrets-management.md` for the full pattern.

## Zod patterns (TypeScript)

### Strict schemas at boundaries

```typescript
import { z } from "zod";

export const CancellationEvent = z.object({
  event_id:         z.string().uuid(),
  party_size:       z.number().int().min(1).max(50),
  cancelled_at:     z.string().datetime(),
  reservation_time: z.string().datetime(),
})
  .strict()
  .refine(
    (e) => new Date(e.cancelled_at) < new Date(e.reservation_time),
    { message: "cancelled_at must precede reservation_time" },
  );

// At the boundary:
const event = CancellationEvent.parse(raw); // throws on invalid
```

`.strict()` is the Zod equivalent of `extra="forbid"` — unknown fields cause a failure rather than being silently dropped.

### Discriminated unions

```typescript
const Decision = z.discriminatedUnion("action", [
  z.object({ action: z.literal("fill_from_waitlist"), target_customer_id: z.string() }),
  z.object({ action: z.literal("offer_alt_time"),     slot_iso: z.string().datetime() }),
  z.object({ action: z.literal("no_action"),          reason: z.string() }),
]);
```

### `safeParse` for graceful error handling

```typescript
const result = CancellationEvent.safeParse(raw);
if (!result.success) {
  logger.warn({ errors: result.error.format() }, "invalid_event");
  await dlq.publish({ raw, errors: result.error.format() });
  await consumer.ack();   // skip the original
  return;
}
const event = result.data;
```

Use `parse` when validation failure should crash; `safeParse` when you want to handle it (DLQ, log, fall through).

## LLM output validation

LLM output is **untrusted**. Always bind to a typed schema before acting on it. Without binding:

- A typo / hallucination produces a malformed JSON the consumer can't parse → crash, no observability into why.
- The model invents fields you have no handler for → silent miss.
- Prompt injection succeeds in changing the decision → unconstrained action on the world.

### Anthropic SDK tool-use binding

```python
import anthropic
from pydantic import TypeAdapter

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    tools=[{
        "name": "submit_decision",
        "description": "Submit the rebooking decision.",
        "input_schema": TypeAdapter(Decision).json_schema(),
    }],
    messages=[...],
)

for block in response.content:
    if block.type == "tool_use" and block.name == "submit_decision":
        decision: Decision = TypeAdapter(Decision).validate_python(block.input)
        break
else:
    raise ValueError("LLM did not produce a decision; retry or escalate")
```

### Higher-level wrappers (Pydantic AI / Instructor)

```python
from pydantic_ai import Agent

agent = Agent("claude-sonnet-4-6", result_type=Decision)
result = await agent.run(prompt)
decision: Decision = result.data
```

These libraries validate the response against the schema and retry on parse failure. Saves boilerplate; same guarantee.

### When validation fails

Do not act on it. The action surface is exactly what the schema constrains — anything outside the schema is undefined behavior. Log the raw output, retry the LLM call (with a clarifying re-prompt) up to N attempts, then escalate to human review or DLQ.

## Error handling matrix

| Boundary | Failure response |
|----------|-----------------|
| HTTP body / query | `422 Unprocessable Entity` with structured error detail |
| Event payload | DLQ the event with validation error in metadata; ACK the original to skip |
| Config / settings | Refuse to start (boot-time crash > silent prod misbehavior) |
| Tool return value | Treat as tool failure; let the agent retry, fall back, or escalate |
| LLM structured output | Don't act; re-prompt up to N times, then DLQ + alert |

### HTTP 422 error shape

```json
{
  "error": "validation_failed",
  "details": [
    { "field": "party_size",        "code": "out_of_range",     "message": "must be ≤ 50" },
    { "field": "reservation_time",  "code": "invalid_datetime", "message": "expected ISO 8601 UTC" }
  ]
}
```

Don't return raw Pydantic / Zod error objects to clients — they leak internal field names and structure. Map errors to a stable schema your API consumers can rely on.

## Performance

Pydantic v2 has a Rust core — typical validation overhead is < 100 µs per model, even for nested shapes. Don't optimize until measured. Things to watch:

- Deeply nested models with `strict=True` and many validators at >10k QPS — measure first.
- `model_construct(...)` skips validation. Use **only** for trusted internal paths (e.g., ORM hydration where the DB is the source of truth) — never for boundary data.
- Repeated validation of the same payload — cache the validated model if it's stable. See `caching-strategies.md`.

## Pitfalls

- **Skipping LLM-output validation** "because the LLM is well-behaved." It isn't, and the cost of binding is small.
- **Lax mode at HTTP boundaries.** Clients send what they want; `extra="allow"` becomes a silent data-loss path the day a typo'd field starts getting populated.
- **Validation in middleware instead of in the handler.** Middleware ties validation to URLs, not to types; the same type used in two routes ends up with two slightly-different validators.
- **Validate once at the boundary, then mutate freely.** Internal corruption goes undetected; mutated objects diverge from the validated shape.
- **Returning raw Pydantic errors to clients.** Exposes internal field names; map to a stable client-facing error vocabulary.
- **Catch-all `except ValidationError: pass`.** The validation failure is the signal; swallowing it is silent data loss.
- **Field-by-field validation in business code.** Once parsed into the model, the invariants are guaranteed — don't re-check them inside every function.

## Where used in repo

- All recipes — boundary validation is universal.
- [recipes/restaurant-rebooking.md](../recipes/restaurant-rebooking.md) — `CancellationEvent` parsed via Pydantic discriminated union (versioned); `RebookingDecision` bound to the Anthropic `submit_decision` tool; `Settings` validated at boot.

## See also

- `schema-evolution.md` — versioned validators for event payloads; discriminated union by `schema_version`.
- `stack/secrets-management.md` — pydantic-settings boot-time validation in production.
- `security-hardening.md` (PR-E, pending) — input validation is one of the four headline production-discipline items.
