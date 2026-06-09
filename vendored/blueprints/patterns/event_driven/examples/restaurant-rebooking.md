# Domain example: Restaurant rebooking (event-driven)

> Concrete worked example for the [Event-Driven pattern](../overview.md), anchored to the [`restaurant-rebooking`](https://github.com/jagguvarma15/agent-deployments/blob/main/docs/recipes/restaurant-rebooking.md) recipe. The companion mini-project lives in [`restaurant_rebooking/`](restaurant_rebooking/) and is fully runnable offline.

## 1. Recipe context

This overlay backs `restaurant-rebooking` — the design-spec recipe for a system that receives `reservation.cancelled` events, decides who's eligible for an instant rebooking, finds an alternative slot across two booking platforms, and notifies the diner. The recipe ships the architecture (consumer loop, role-by-role wiring, observability hooks) and the framework choices (LangGraph + Mastra); this overlay fills in the **business-logic layer** the LLM otherwise has to invent: what `policy_lookup.is_eligible()` actually does, what shape an `EligibilityDecision` takes, what a notifier prompt looks like in production.

Read the recipe first for the architecture, then this overlay for the concrete shapes.

## 2. Concrete domain glossary

| Term | Definition |
|------|------------|
| **Party** | The diner whose reservation was cancelled. Modeled with `customer_id`, `tier`, `locale`, `sms_opt_in`. |
| **Reservation** | The original booking (id, venue, party_size, `starts_at`, source platform). Cancelled at the start of the flow. |
| **Slot** | One alternative reservation slot returned by a booking-platform adapter — `(venue_id, starts_at, duration_minutes, capacity_for_party, source)`. |
| **EligibilityDecision** | The eligibility role's structured output — `{eligible, reason_code, rationale, requires_manager_approval}`. |
| **SlotRanking** | The search role's output — a sorted `list[Slot]` plus a one-sentence `ranking_rationale`. |
| **NotificationDraft** | The notifier role's output before send — `{channel, body, requires_translation}`. |
| **RebookingOutcome** | The actor's terminal result — `{action, new_reservation_id?, notification_sent, rationale}` where `action ∈ {rebooked, notify_host_only, declined, dlq}`. |

## 3. Concrete data

Three example `CancellationEvent` payloads the consumer receives:

```json
{"reservation_id": "rsv_123", "venue_id": "venue_42", "customer_id": "cust_7",  "party_size": 4, "starts_at": "2026-06-05T19:00:00+00:00", "source": "resy"}
{"reservation_id": "rsv_124", "venue_id": "venue_42", "customer_id": "cust_13", "party_size": 6, "starts_at": "2026-06-05T19:00:00+00:00", "source": "resy"}
{"reservation_id": "rsv_125", "venue_id": "venue_999", "customer_id": "cust_11", "party_size": 2, "starts_at": "2026-06-05T19:00:00+00:00", "source": "opentable"}
```

Three corresponding `Case` enrichments after the `intake` role runs (one row per case, showing the typed fields the decider sees):

```json
{"party": {"customer_id": "cust_7",  "name": "Ada Lovelace", "tier": "platinum",  "sms_opt_in": true}, "reservation": {"reservation_id": "rsv_123", "party_size": 4, "starts_at": "2026-06-05T19:00:00+00:00"}}
{"party": {"customer_id": "cust_13", "name": "Alan Turing",  "tier": "standard",  "sms_opt_in": false}, "reservation": {"reservation_id": "rsv_124", "party_size": 6, "starts_at": "2026-06-05T19:00:00+00:00"}}
{"party": {"customer_id": "cust_11", "name": "Grace Hopper", "tier": "gold",      "sms_opt_in": true}, "reservation": {"reservation_id": "rsv_125", "party_size": 2, "starts_at": "2026-06-05T19:00:00+00:00"}}
```

Three corresponding `RebookingOutcome` results (the actor's terminal state):

```json
{"action": "rebooked",          "new_reservation_id": "rsv_new_cust_7",  "notification_sent": true,  "rationale": "Rebooked to resy slot at 2026-06-05T19:00:00+00:00."}
{"action": "notify_host_only",  "new_reservation_id": null,              "notification_sent": true,  "rationale": "Standard tier limited to parties of 4 for instant rebooking."}
{"action": "declined",          "new_reservation_id": null,              "notification_sent": true,  "rationale": "No alternative slots within window."}
```

## 4. Concrete tool implementations

Full Python in [`restaurant_rebooking/tools.py`](restaurant_rebooking/tools.py). The contract:

- **`ResyAdapter.search_slots(reservation, window_hours=4) -> list[Slot]`** — wraps the Resy availability endpoint. Real shape: `GET https://api.resy.com/3/venues/{venue_id}/availability?party_size={n}&start={iso}&end={iso}`. The mock body returns an in-memory inventory filtered by `(venue_id, time window, party_size capacity)`.
- **`OpenTableAdapter.search_slots(reservation, window_hours=4) -> list[Slot]`** — wraps the OpenTable Affiliate API. Real shape: `GET https://platform.otrest.com/v1/restaurants/{venue_id}/availability?datetime={iso}&partySize={n}`. Same mock pattern.
- **`policy_is_eligible(party, reservation) -> EligibilityDecision`** — deterministic policy: `tier == standard AND party_size > 4` → not eligible (`tier_too_low`, requires manager approval); `tier ∈ {gold, platinum}` → eligible; otherwise eligible. Real version would hit a customer-profile service.
- **`notifier_send_sms(party, draft) -> {delivered, channel}`** — pretends to deliver via Twilio. Honors `sms_opt_in=False` by no-op'ing with `"reason": "sms_opt_out"`. Real shape: `POST https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json`.

Each tool keeps the call signature and return type stable when the body is swapped for a real implementation — that's the contract the recipe pins.

## 5. Per-role prompts

Full strings in [`restaurant_rebooking/prompts.py`](restaurant_rebooking/prompts.py). Each prompt declares typed input/output schemas (the recipe's B4-shaped contract).

- **`intake`** — input: `Event`. output: `Case`. Trusts the platform's source-of-truth ids; drops free-text fields; emits a one-sentence `correlation_id` summary for observability.
- **`eligibility`** — input: `Case`. output: `EligibilityDecision`. Deterministic rules listed in the prompt body; the LLM mostly assembles the `rationale`. Never write free-form prose into `reason_code` (the router dispatches off the exact string).
- **`search`** — input: enriched `Case`. output: `SlotRanking`. Sort key: closest start time → same source → smaller `capacity_for_party`. Never invent `slot.starts_at` — use only adapter-returned slots.
- **`notifier`** — input: `Case + RebookingOutcome`. output: `NotificationDraft`. Body rules vary by `outcome.action`; channel selection respects `sms_opt_in`; `locale not in {"en-US", "en-GB"}` flips `requires_translation`.

Sample dialog for `eligibility` (showing the LLM's structured-output round-trip):

```
[system] You are the eligibility decider...
[user]   Case: {"party": {"customer_id": "cust_13", "tier": "standard", ...}, "reservation": {"party_size": 6, ...}}
[assistant — JSON]
{"eligible": false, "reason_code": "tier_too_low", "rationale": "Standard tier limited to parties of 4 for instant rebooking.", "requires_manager_approval": true}
```

## 6. Decision schemas

Pydantic v2 models in [`restaurant_rebooking/schemas.py`](restaurant_rebooking/schemas.py):

```python
class EligibilityDecision(BaseModel):
    eligible: bool
    reason_code: str          # tier_too_low | policy_violation | eligible
    rationale: str
    requires_manager_approval: bool = False


class SlotRanking(BaseModel):
    slots: list[Slot]
    ranking_rationale: str
    # `best` is a derived property; the first element when slots is non-empty.


class NotificationDraft(BaseModel):
    channel: str = "sms"      # sms | email | push
    body: str
    requires_translation: bool = False


class RebookingOutcome(BaseModel):
    action: str               # rebooked | notify_host_only | declined | dlq
    new_reservation_id: str | None = None
    notification_sent: bool = False
    rationale: str
```

These extend the canonical Event-Driven state in [`../schemas/state.py`](../schemas/state.py): `Event`, `Case`, `Outcome` from the pattern's state module wrap the domain types here.

## 7. End-to-end walkthrough

Trace from the first example payload (Ada Lovelace, platinum tier, party of 4, Resy):

1. **Consume.** The consumer loop lifts the JSON payload off the queue. `Event.event_id` is the dedup key. (Pattern wiring; see [`../overview.md`](../overview.md).)
2. **Enrich.** [`main.enrich(payload)`](restaurant_rebooking/main.py) calls `lookup_party("cust_7")` → returns the typed `Party(name="Ada Lovelace", tier=platinum)`. The `Reservation` is built directly from the payload.
3. **Decide eligibility.** [`policy_is_eligible(party, reservation)`](restaurant_rebooking/tools.py) sees `tier == platinum` → returns `EligibilityDecision(eligible=True, reason_code="eligible", rationale="Platinum tier — instant rebooking allowed.")`.
4. **Search slots.** [`main.rank_slots`](restaurant_rebooking/main.py) calls both adapters; `ResyAdapter.search_slots` returns one slot at `19:00`, `OpenTableAdapter.search_slots` returns one at `19:15`. Sort by `(time_delta, same_source, capacity)` → the Resy `19:00` slot wins (zero time delta + same source as original).
5. **Act.** The actor assigns `new_reservation_id="rsv_new_cust_7"`, then calls [`_draft_notification`](restaurant_rebooking/main.py) (stand-in for the notifier role's structured-output LLM call) which produces a `NotificationDraft(channel="sms", body="Hi Ada Lovelace, your reservation at venue_42 was cancelled. We've rebooked you for 2026-06-05T19:00:00+00:00 (was 2026-06-05T19:00:00+00:00). Sorry for the shuffle.")`.
6. **Notify.** [`notifier_send_sms(party, draft)`](restaurant_rebooking/tools.py) sees `sms_opt_in=True` → returns `{"delivered": True, "channel": "sms"}`.
7. **Emit terminal `RebookingOutcome`.** `action="rebooked"`, `new_reservation_id="rsv_new_cust_7"`, `notification_sent=True`, `rationale="Rebooked to resy slot at 2026-06-05T19:00:00+00:00."` The consumer loop persists this and may emit a follow-up `reservation.rebooked` event.

The walkthrough's test suite ([`restaurant_rebooking/test_walkthrough.py`](restaurant_rebooking/test_walkthrough.py)) covers the four canonical paths: platinum-rebook, standard-tier-too-large, no-slots-decline, unknown-customer-DLQ. All four run offline.

## Run it

```bash
cd patterns/event_driven/examples/restaurant_rebooking
uv run --with pydantic python -m patterns.event-driven.examples.restaurant_rebooking.main
# or
uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v
```
