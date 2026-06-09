# Domain example: Trip booking (saga)

> Concrete worked example for the [Saga pattern](../overview.md). The companion mini-project lives in [`trip_booking/`](trip_booking/) and runs offline.

## 1. Recipe context

No validated `agent-deployments` recipe anchors this overlay yet; the shape below is proposed. A future recipe ("itinerary-orchestrator" or similar) would lift the trip-booking saga into a deployable agent with real Amadeus / Sabre adapters; this overlay is the business-logic shape that recipe would inherit. The `restaurant-rebooking` recipe contains a different saga (cancellation-rebooking) but is already anchored to the event-driven overlay, so the trip-booking domain stays a clean separate example here.

Trip booking is the archetypal saga shape: every forward step has a vendor-side reservation that needs an explicit cancel, the steps are ordered (you can't book a hotel for a flight you haven't confirmed yet), and the three terminal states the pattern documents — `completed`, `compensated`, `partially_compensated` — each correspond to a real operational outcome (trip booked end-to-end; trip failed mid-saga and everything was cleanly unwound; trip failed mid-saga and one cancellation itself failed, leaving a residual booking the runbook owner must reconcile).

Read the framework-agnostic sibling at [`../code/python/saga.py`](../code/python/saga.py) first for the saga loop's control flow; then this overlay for the trip-domain shapes and the optional coordinator role.

## 2. Concrete domain glossary

| Term | Definition |
|------|------------|
| **LegKind** | The three leg kinds — `flight / hotel / car`. Drives adapter dispatch and compensation. |
| **Leg** | One leg the saga books — `leg_id`, `kind`, `vendor`, `starts_at`, `ends_at`, `params`. |
| **Reservation** | A successful adapter booking — `leg_id`, `confirmation` (vendor-issued code), `price_cents`, `booked_at`. |
| **CompensationOutcome** | Per-leg cancellation status — `leg_id`, `succeeded`, optional `error`, `retry_count`. |
| **SagaTerminalState** | `completed / compensated / partially_compensated`. The terminal state IS the outcome — not an input the coordinator picks. |
| **TripBooking** | The saga's input — `saga_id`, exactly three legs (`min_length=3, max_length=3`). |
| **TripResult** | The saga's typed output — `saga_id`, `terminal_state`, `reservations`, `compensation_outcomes`, optional `failure_leg_id`. |

## 3. Concrete data

Three example saga runs, one per terminal state:

```json
{"saga_id": "trip_001", "outcome": "completed"}
{"saga_id": "trip_002", "outcome": "compensated (car booking failed -> flight + hotel cancelled cleanly)"}
{"saga_id": "trip_003", "outcome": "partially_compensated (car booking failed -> hotel cancel raised vendor_timeout, flight cancel succeeded)"}
```

Each `TripBooking` shares the same canonical three-leg shape:

```json
{
  "saga_id": "<id>",
  "legs": [
    {"leg_id": "<id>-flight", "kind": "flight", "vendor": "alpha-air",   "starts_at": "...", "ends_at": "...", "params": {"route": "SFO-JFK"}},
    {"leg_id": "<id>-hotel",  "kind": "hotel",  "vendor": "beta-stays",  "starts_at": "...", "ends_at": "...", "params": {"room": "queen"}},
    {"leg_id": "<id>-car",    "kind": "car",    "vendor": "gamma-cars",  "starts_at": "...", "ends_at": "...", "params": {"size": "midsize"}}
  ]
}
```

The `trip_003` `TripResult` (the partial-compensation case):

```json
{
  "saga_id": "trip_003",
  "terminal_state": "partially_compensated",
  "reservations": [
    {"leg_id": "trip_003-flight", "confirmation": "FL-003-alp", ...},
    {"leg_id": "trip_003-hotel",  "confirmation": "HT-003-bet", ...}
  ],
  "compensation_outcomes": [
    {"leg_id": "trip_003-hotel",  "succeeded": false, "error": "vendor_timeout"},
    {"leg_id": "trip_003-flight", "succeeded": true}
  ],
  "failure_leg_id": "trip_003-car"
}
```

## 4. Concrete tool implementations

Full Python in [`trip_booking/tools.py`](trip_booking/tools.py).

- **`FlightAdapter.book(saga_id, leg_id, vendor) -> Reservation`** / **`FlightAdapter.cancel(saga_id, leg_id) -> None`** — the flight booking pair. Mock returns a typed `Reservation`; cancellation removes from the in-process booking table. Real adapters wrap Amadeus / Sabre. Honours `_BOOK_FAILURES` and `_COMPENSATE_FAILURES` for the walkthrough scenarios.
- **`HotelAdapter.book(...)` / `HotelAdapter.cancel(...)`** — same shape, separate canned-failure table.
- **`CarAdapter.book(...)` / `CarAdapter.cancel(...)`** — same.
- **`AuditLog.append(saga_id, event, detail)`** — in-memory append-only log. Real impl writes to Postgres + ships to S3 nightly; the contract is the same. Used by the coordinator to record every booking, cancellation, and coordinator-decision event so the runbook owner has a trace to follow.

Three dispatch helpers (`book_leg`, `cancel_leg`, `adapter_for_kind`) keep the coordinator code uniform across the three leg kinds.

Vendor confirmation codes follow a `{KIND_PREFIX}-{SAGA_TAIL}-{VENDOR_PREFIX}` shape (`FL-001-alp`, `HT-001-bet`) so logs are scannable.

## 5. Per-role prompts

Full strings in [`trip_booking/prompts.py`](trip_booking/prompts.py). The forward saga is deterministic — no LLM role on the happy path.

The one optional LLM role is the **coordinator**: invoked when a compensation itself fails, decides whether to keep compensating remaining legs or stop with a partial. Input: the failed `CompensationOutcome`, the already-attempted outcomes, and the still-pending leg ids. Output: a `CoordinatorDecision` (`action` is `continue_compensating` or `stop_with_partial`; rationale; optional `notify_runbook` when stopping).

Decision policy (mirrored in `_coordinator_decision` for the offline stub):

- Recoverable error (`vendor_timeout`, etc.) **and** pending legs remain -> `continue_compensating`. A transient vendor failure on one leg shouldn't block undoing the others; the runtime can retry the failed compensation later.
- Permanent error or no pending legs -> `stop_with_partial`. The terminal state is `partially_compensated`; the named runbook (`rb_trip_partial_compensation`) is paged to handle the residual booking.

Sample dialog:

```
[system] You are the saga coordinator. You are invoked ONLY when a compensation itself fails...
[user]   Failed: CompensationOutcome(leg_id="trip_003-hotel", succeeded=False, error="vendor_timeout")
         Already attempted: []
         Pending leg ids: ["trip_003-flight"]
[assistant — JSON]
{"action": "continue_compensating", "rationale": "vendor_timeout is retryable; do not block remaining undo work.", "notify_runbook": null}
```

## 6. Decision schemas

Pydantic v2 models in [`trip_booking/schemas.py`](trip_booking/schemas.py):

```python
class Leg(BaseModel):
    leg_id: str
    kind: LegKind                # flight | hotel | car
    vendor: str
    starts_at: datetime
    ends_at: datetime
    params: dict[str, str] = {}


class Reservation(BaseModel):
    leg_id: str
    confirmation: str
    price_cents: int
    booked_at: datetime


class CompensationOutcome(BaseModel):
    leg_id: str
    succeeded: bool
    error: str | None = None
    retry_count: int = 0


class TripResult(BaseModel):
    saga_id: str
    terminal_state: SagaTerminalState     # completed | compensated | partially_compensated
    reservations: list[Reservation] = []
    compensation_outcomes: list[CompensationOutcome] = []
    failure_leg_id: str | None = None
```

These compose with the canonical Saga state in [`../schemas/state.py`](../schemas/state.py): a recipe-level `SagaState` carries `SagaStep` + `Compensation` per leg; this overlay's `Reservation` and `CompensationOutcome` are typed views of those shapes with vendor + price added.

## 7. End-to-end walkthrough

Three traces from `book_trip(...)`:

### Happy path (`trip_001`)

1. **Caller invokes** `book_trip(_sample_booking("trip_001"))`. `main.py:book_trip`.
2. **Forward loop.** Flight book -> `FL-001-alp`; hotel book -> `HT-001-bet`; car book -> `CR-001-gam`.
3. **Terminal state.** No failure -> `TripResult(terminal_state=completed, reservations=[3], compensation_outcomes=[])`.

### Compensated path (`trip_002`)

1. **Forward loop.** Flight + hotel book successfully. Car booking raises `RuntimeError("car booking failed: vendor=gamma-cars")`.
2. **Failure detected.** `failure_leg_id = "trip_002-car"`. Compensation begins on `completed = [flight, hotel]`.
3. **Compensation walks in reverse.** Hotel cancel -> succeeds; flight cancel -> succeeds. `any_failure = False`.
4. **Terminal state.** `TripResult(terminal_state=compensated, reservations=[2], compensation_outcomes=[hotel(ok), flight(ok)], failure_leg_id="trip_002-car")`.

### Partially-compensated path (`trip_003`)

1. **Forward loop.** Flight + hotel book successfully. Car booking raises (same canned scenario as `trip_002`).
2. **Compensation begins on `[flight, hotel]`.**
3. **Hotel cancel fails.** `_COMPENSATE_FAILURES[("trip_003", "hotel")] = "vendor_timeout"`. The outcome is `CompensationOutcome(leg_id="trip_003-hotel", succeeded=False, error="vendor_timeout")`.
4. **Coordinator decision.** `_coordinator_decision(failed, pending=["trip_003-flight"])` classifies `vendor_timeout` as recoverable and sees a pending leg -> `continue_compensating`.
5. **Flight cancel.** Proceeds and succeeds.
6. **Terminal state.** `any_failure = True` -> `TripResult(terminal_state=partially_compensated, ...)`. The audit log carries the `coordinator_decision` event; the named runbook (`rb_trip_partial_compensation`) is paged to reconcile the residual hotel booking.

The test suite ([`trip_booking/test_walkthrough.py`](trip_booking/test_walkthrough.py)) covers all three terminal states; the third test exercises `_compensate(...)` directly with a hand-built `completed` list so the partial-compensation path is independently verifiable.

## Run it

```bash
cd patterns/saga/examples/trip_booking
uv run --with pydantic python -m patterns.saga.examples.trip_booking.main
# or
uv run --with pydantic --with pytest python -m pytest test_walkthrough.py -v
```
