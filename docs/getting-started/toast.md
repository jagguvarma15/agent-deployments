# Toast

> Restaurant point-of-sale and reservation platform. Toast does publish an API, but reservation-create endpoints are gated to active merchant accounts.

**Signup**: https://pos.toasttab.com/ (merchant signup; not relevant for the mock).

## Status

`agent-scaffold` uses a **mock adapter** for Toast in the [restaurant-rebooking recipe](../recipes/restaurant-rebooking.md). The mock simulates availability search, booking, and cancellation deterministically — no external calls, no rate limits, no Toast merchant account required.

`doctor` does not probe Toast; there's nothing to probe. The `external_services` entry in the recipe declares Toast with `kind: mock` so the plan panel shows ✓ without a network check.

## If you have a Toast partner / merchant token

Toast offers OAuth-based partner APIs and merchant-scoped access tokens. If you have one:

1. Set `TOAST_API_KEY` and `TOAST_MERCHANT_GUID` in `.env.local`.
2. Implement `src/adapters/toast.py` against the [Toast developer docs](https://doc.toasttab.com/openapi/) (`reservations` and `availability` endpoints).
3. The mock adapter is bypassed automatically when `TOAST_API_KEY` is set.

The recipe's adapter ABC documents the four methods the mock and any real adapter must implement: `search_availability`, `book`, `cancel`, `confirm_existing`.

## See also

- [`docs/recipes/restaurant-rebooking.md`](../recipes/restaurant-rebooking.md) — full recipe, mock adapter section
- [`resy.md`](resy.md), [`opentable.md`](opentable.md) — same mock-adapter pattern
- Toast developer docs: https://doc.toasttab.com/openapi/
