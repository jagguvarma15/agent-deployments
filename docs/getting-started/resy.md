# Resy

> Restaurant reservation platform (owned by American Express). No public booking API as of 2026.

**Signup**: not applicable (no public API).

## Status

`agent-scaffold` uses a **mock adapter** for Resy in the [restaurant-rebooking recipe](../recipes/restaurant-rebooking.md). The mock simulates availability search, booking, and cancellation deterministically — no external calls, no rate limits.

`doctor` does not probe Resy; there's nothing to probe. The `external_services` entry in the recipe declares Resy with `kind: mock` so the plan panel shows ✓ without a network check.

## If you have a partner API key

Resy offers a partner / B2B API by invitation only. If you have one:

1. Set `RESY_API_KEY` in `.env.local`.
2. Implement `src/adapters/resy.py` against your partner contract (the recipe defines the abstract `ReservationPlatform` interface).
3. The mock adapter is bypassed automatically when `RESY_API_KEY` is set.

The recipe's adapter ABC documents the four methods the mock and any real adapter must implement: `search_availability`, `book`, `cancel`, `confirm_existing`.

## See also

- [`docs/recipes/restaurant-rebooking.md`](../recipes/restaurant-rebooking.md) — full recipe, mock adapter section
- [`opentable.md`](opentable.md), [`toast.md`](toast.md) — same mock-adapter pattern for the other two platforms
