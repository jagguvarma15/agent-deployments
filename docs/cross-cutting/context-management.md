# Cross-cutting: Context Management

**Concern:** Hold a bounded multi-turn conversation — accept the `/chat` contract's `history` and deterministically trim it to the recipe's context budget before every model call.
**Library:** stdlib only (Py) / stdlib only (TS) — no tokenizer dependency; the budget uses a chars/4 estimate.
**Lives in:** Inline below — emit as `agent/context_window.py` (Py) or `src/contextWindow.ts` (TS) and call it in the `/chat` handler.

## What it provides

- **`ChatTurn`** — the shape of one prior turn, mirroring the [`/chat` contract](../reference/chat-contract.md)'s history items: `{role: "user" | "agent", text: str}`, oldest first.
- **`trim_history(history, *, budget_tokens, keep_last_turns=2)`** (Py) / **`trimHistory(history, {budgetTokens, keepLastTurns})`** (TS) — a deterministic token-budget sliding window with four guarantees:
  - **Whole exchanges only.** Turns are grouped into user-led exchanges (one user turn plus the agent turns that answer it) and kept or dropped as a unit — the model never sees an answer without its question.
  - **Newest wins, contiguously.** Exchanges are retained from newest to oldest while the estimate fits; the survivors are always a contiguous suffix of the conversation, never a gappy sample.
  - **A bounded floor, not amnesia.** The newest `keep_last_turns` user-led exchanges are kept even when they exceed the budget — up to `max(budget_tokens, FLOOR_TOKEN_CAP)` estimated tokens — so a too-small budget degrades to short memory while a pathologically oversized exchange is dropped rather than re-billed on every call. An agent-led head group (an opening greeting) is never floor-protected.
  - **Pure function.** Same history + same budget = same output. No tokenizer version drift, no clock, no randomness.
- **`estimate_tokens(text)`** — `max(1, len(text) // 4)`. The chars/4 heuristic over-counts terse code and under-counts dense Unicode relative to real BPE tokenizers; that is acceptable because recipe budgets carry headroom (the default mode's `input_max: 80000` sits well inside the model's real window). Use one estimator everywhere — see Pitfalls.
- The **latest user message is never trimmed**: it travels as `message`, outside `history`, and is appended after trimming.

## Why this exists

Generated agents were stateless single-turn services: the `/chat` contract declared an optional `history` nothing sent, and every recipe's `runtime_modes[<mode>].context_budget` declared an `input_max` nothing read. This doc closes that loop — history in, bounded prompt out. Unbounded history is the failure mode on both axes: quality (old turns crowd out the system prompt and retrieved context) and cost (every stale turn is re-billed on every call).

Of the four context levers — select, compress, prune, persist — this doc ships **select + prune** only. Compression (summarize-and-replace) and persistence (long-term stores) are the upgrade path below.

## How to use

### Python (FastAPI + Pydantic AI)

The emitted `core.io_schema` package already gives `ChatRequest` a `history: list[ChatTurn]` field. In the `/chat` handler, trim, convert, and pass `message_history`:

```python
from agent.context_window import (
    context_input_max,
    estimate_tokens,
    keep_last_turns_floor,
    to_model_messages,
    trim_history,
)

@app.post("/chat")
async def chat(req: ChatRequest) -> ChatResponse:
    budget = context_input_max() - estimate_tokens(SYSTEM_PROMPT) - estimate_tokens(req.message)
    trimmed = trim_history(
        req.history, budget_tokens=budget, keep_last_turns=keep_last_turns_floor()
    )
    result = await agent.run(req.message, message_history=to_model_messages(trimmed))
    return ChatResponse(reply=result.output)
```

`to_model_messages` builds the **typed** list Pydantic AI requires — `ModelRequest(parts=[UserPromptPart(...)])` for `user` turns, `ModelResponse(parts=[TextPart(...)])` for `agent` turns. Do not pass raw `{"role": ..., "content": ...}` dicts: mixing OpenAI-shaped messages into `message_history` results in a silent validation failure where the agent forgets prior turns (see the Upgrade gotchas in [`frameworks/pydantic-ai.md`](../frameworks/pydantic-ai.md)).

### TypeScript (Hono + Vercel AI SDK)

Parse `{message, history}` from the request body and replace `prompt:` with `messages:`:

```typescript
import {
  contextInputMax,
  estimateTokens,
  keepLastTurnsFloor,
  toCoreMessages,
  trimHistory,
} from "./contextWindow";

app.post("/chat", async (c) => {
  const { message, history = [] } = await c.req.json();
  const budget = contextInputMax() - estimateTokens(SYSTEM_PROMPT) - estimateTokens(message);
  const trimmed = trimHistory(history, { budgetTokens: budget, keepLastTurns: keepLastTurnsFloor() });
  const { text } = await generateText({
    model,
    system: SYSTEM_PROMPT,
    messages: [...toCoreMessages(trimmed), { role: "user", content: message }],
  });
  return c.json({ reply: text });
});
```

Note the role mapping: the wire role `agent` becomes the SDK role `assistant`. `toCoreMessages` does this; hand-rolled mappings that forward `agent` verbatim are rejected by the SDK.

## Choosing the budget

- `CONTEXT_INPUT_MAX` defaults from the recipe's `runtime_modes[<active mode>].context_budget.input_max` (80000 in the default mode, 32000 in `local_only`). The generator should bake the recipe value into `.env` / compose as `CONTEXT_INPUT_MAX=${CONTEXT_INPUT_MAX:-<input_max>}`.
- **Budget the history slice, not the whole window.** Pass `budget_tokens = CONTEXT_INPUT_MAX - estimate(system prompt) - estimate(latest message) - reserve`, where `reserve` covers whatever else enters the prompt: retrieved chunks, tool schemas, injected memories. In RAG recipes retrieval is the bigger spender — history should be the first thing squeezed, which is exactly what a small `budget_tokens` does.

## Configuration via env

| Var | Default | Effect |
|-----|---------|--------|
| `CONTEXT_INPUT_MAX` | recipe `context_budget.input_max` (else `80000`) | Token budget the assembled prompt must fit; history is trimmed against what remains after the system prompt, latest message, and reserve |
| `CONTEXT_KEEP_LAST_TURNS` | `2` | Floor: newest user-led exchanges kept even when over budget, bounded by `FLOOR_TOKEN_CAP` |

## Tests

Pure-function table tests (no mocks needed):

- empty history returns empty;
- history under budget is returned unchanged;
- over budget, the **oldest** exchanges are dropped first and the survivors are a contiguous suffix;
- an agent turn is never returned without the user turn that prompted it;
- with `budget_tokens=0`, exactly the `keep_last_turns` newest user-led exchanges survive (each under `FLOOR_TOKEN_CAP`);
- an agent-led head group is dropped at `budget_tokens=0` (never floor-protected);
- a single exchange larger than `FLOOR_TOKEN_CAP` is dropped entirely at `budget_tokens=0` (the floor is bounded);
- calling twice with the same input yields identical output.

Handler test: POST `/chat` with 200 synthetic 2 KB turns in `history`, mock the model call, and assert the list it received fits the budget.

## Pitfalls

- **Splitting an exchange.** Trimming individual turns leaves the model an answer with no question (or vice versa) — always drop whole user-led exchanges.
- **Trimming after concatenation.** Once history is string-formatted into a prompt you can only truncate mid-sentence. Trim the structured list, then format.
- **Client-side-only trimming.** The bundled UIs cap what they send as a courtesy, but the wire accepts anything — the backend trim is the authoritative one.
- **Raw dicts into Pydantic AI.** `message_history` takes typed messages; OpenAI-shaped dicts fail silently and the agent forgets prior turns.
- **Mixed estimators.** Counting with a real tokenizer in one code path and chars/4 in another makes the budget mean two different things. Pick one estimator everywhere; this doc picks chars/4.
- **A sliding window is not memory.** Facts older than the window are gone — that is the contract of this doc. Durable per-user facts belong in a memory store (see the [memory-assistant recipe](../recipes/memory-assistant.md) and the blueprints memory primitive), not in an ever-longer history.

## Upgrade path: summarize-and-replace

When the window drops turns you still need, the next lever is compression: summarize the evicted prefix into one synthetic turn and prepend it to the trimmed window. The shape is documented in [`agent-blueprints/primitives/memory/implementation.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/memory/implementation.md) (summarize-and-replace). It trades this doc's determinism for retention and adds a model call on the trim path — adopt it deliberately, not by default. Future work may standardize it behind the catalog's reserved `context_assembly` port concern.

## Reference Implementation

<details>
<summary>Python — <code>context_window.py</code></summary>

```python
"""Deterministic token-budget trimming for /chat conversation history.

Pure functions: same history + same budget -> same output. No tokenizer
dependency -- the budget uses a chars/4 estimate and expects the headroom
already present in the recipe's context_budget.

Works on any turn shape exposing ``role`` ("user" | "agent") and ``text``
attributes, e.g. the ChatTurn model emitted by core.io_schema.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol, TypeVar

if TYPE_CHECKING:
    from pydantic_ai.messages import ModelMessage


class Turn(Protocol):
    """One prior conversation turn, as carried by the /chat contract."""

    role: str  # "user" | "agent"
    text: str


T = TypeVar("T", bound=Turn)


def context_input_max(default: int = 80_000) -> int:
    """Token budget for the assembled prompt, from CONTEXT_INPUT_MAX.

    The generator bakes the recipe's context_budget.input_max in as the env
    default; a missing or malformed value falls back to ``default``.
    """
    try:
        value = int(os.environ.get("CONTEXT_INPUT_MAX", ""))
    except ValueError:
        return default
    return value if value > 0 else default


def keep_last_turns_floor(default: int = 2) -> int:
    """Floor of newest exchanges kept even over budget (CONTEXT_KEEP_LAST_TURNS)."""
    try:
        value = int(os.environ.get("CONTEXT_KEEP_LAST_TURNS", ""))
    except ValueError:
        return default
    return value if value >= 0 else default


def estimate_tokens(text: str) -> int:
    """Deterministic chars/4 estimate. Over/under-counts vs real BPE; budgets carry headroom."""
    return max(1, len(text) // 4)


FLOOR_TOKEN_CAP = 16_000
"""Hard ceiling (estimated tokens) on what floor protection may retain.

The keep_last_turns floor deliberately overrides budget_tokens so a
too-small budget degrades to short memory instead of no memory -- but
without a ceiling a single pathological multi-megabyte exchange would ride
the floor into every model call forever. Floor-kept exchanges therefore
stop at max(budget_tokens, FLOOR_TOKEN_CAP): amnesia beats an unbounded
bill.
"""


def trim_history(
    history: Sequence[T],
    *,
    budget_tokens: int,
    keep_last_turns: int = 2,
) -> list[T]:
    """Keep the newest whole user-led exchanges that fit ``budget_tokens``.

    Guarantees: exchanges are kept or dropped whole (never a dangling
    reply); the survivors are a contiguous suffix of the conversation; the
    newest ``keep_last_turns`` user-led exchanges survive even when over
    budget, up to a hard cap of ``max(budget_tokens, FLOOR_TOKEN_CAP)``
    estimated tokens (an agent-led head group is never floor-protected, and
    a pathologically oversized exchange is dropped, not kept); and the
    result is a pure function of the inputs.
    """
    if not history:
        return []
    hard_cap = max(budget_tokens, FLOOR_TOKEN_CAP)
    exchanges = _group_exchanges(history)
    kept: list[list[T]] = []
    spent = 0
    floor_used = 0
    for exchange in reversed(exchanges):
        cost = sum(estimate_tokens(turn.text) for turn in exchange)
        user_led = exchange[0].role == "user"
        fits_budget = spent + cost <= budget_tokens
        floor_protected = user_led and floor_used < keep_last_turns and spent + cost <= hard_cap
        if not fits_budget and not floor_protected:
            break
        kept.append(exchange)
        spent += cost
        if user_led:
            floor_used += 1
    kept.reverse()
    return [turn for exchange in kept for turn in exchange]


def _group_exchanges(history: Sequence[T]) -> list[list[T]]:
    """Group oldest-first turns into user-led exchanges.

    An exchange is one user turn plus every agent turn that follows it before
    the next user turn. Agent turns arriving before any user turn (an opening
    greeting) form their own head group.
    """
    exchanges: list[list[T]] = []
    for turn in history:
        if turn.role == "user" or not exchanges:
            exchanges.append([turn])
        else:
            exchanges[-1].append(turn)
    return exchanges


def to_model_messages(history: Sequence[Turn]) -> list[ModelMessage]:
    """Convert wire turns to Pydantic AI's typed message list.

    The only framework-specific function in this module -- delete it (and
    convert at the call site) on non-Pydantic-AI stacks. Raw role/content
    dicts must never be passed to ``message_history``: they fail silently
    and the agent forgets prior turns.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        TextPart,
        UserPromptPart,
    )

    messages: list[ModelMessage] = []
    for turn in history:
        if turn.role == "user":
            messages.append(ModelRequest(parts=[UserPromptPart(content=turn.text)]))
        else:
            messages.append(ModelResponse(parts=[TextPart(content=turn.text)]))
    return messages
```

</details>

<details>
<summary>TypeScript — <code>contextWindow.ts</code></summary>

```typescript
/**
 * Deterministic token-budget trimming for /chat conversation history.
 *
 * Pure functions: same history + same budget -> same output. No tokenizer
 * dependency -- the budget uses a chars/4 estimate and expects the headroom
 * already present in the recipe's context_budget.
 */

/** One prior conversation turn, as carried by the /chat contract. */
export interface ChatTurn {
  role: "user" | "agent";
  text: string;
}

/** Strict base-10 integer from env; empty, missing, or malformed -> fallback. */
function intFromEnv(name: string, fallback: number, minimum: number): number {
  const raw = (process.env[name] ?? "").trim();
  // Rejects "", "1e5", "0x10", "-1" -- Number("") is 0 and Number() accepts
  // exotic notations the Python twin's int() refuses; both languages must
  // read the same env file identically.
  if (!/^\d+$/.test(raw)) return fallback;
  const value = parseInt(raw, 10);
  return Number.isSafeInteger(value) && value >= minimum ? value : fallback;
}

/**
 * Token budget for the assembled prompt, from CONTEXT_INPUT_MAX.
 * The generator bakes the recipe's context_budget.input_max in as the env
 * default; a missing or malformed value falls back to `fallback`.
 */
export function contextInputMax(fallback = 80_000): number {
  return intFromEnv("CONTEXT_INPUT_MAX", fallback, 1);
}

/** Floor of newest user-led exchanges kept even over budget (CONTEXT_KEEP_LAST_TURNS). */
export function keepLastTurnsFloor(fallback = 2): number {
  return intFromEnv("CONTEXT_KEEP_LAST_TURNS", fallback, 0);
}

/** Deterministic chars/4 estimate. Over/under-counts vs real BPE; budgets carry headroom. */
export function estimateTokens(text: string): number {
  return Math.max(1, Math.floor(text.length / 4));
}

/**
 * Hard ceiling (estimated tokens) on what floor protection may retain.
 * The keepLastTurns floor deliberately overrides budgetTokens so a
 * too-small budget degrades to short memory instead of no memory -- but
 * without a ceiling a single pathological multi-megabyte exchange would
 * ride the floor into every model call forever. Floor-kept exchanges stop
 * at max(budgetTokens, FLOOR_TOKEN_CAP): amnesia beats an unbounded bill.
 */
export const FLOOR_TOKEN_CAP = 16_000;

/**
 * Keep the newest whole user-led exchanges that fit `budgetTokens`.
 *
 * Guarantees: exchanges are kept or dropped whole (never a dangling reply);
 * the survivors are a contiguous suffix of the conversation; the newest
 * `keepLastTurns` user-led exchanges survive even when over budget, up to
 * a hard cap of max(budgetTokens, FLOOR_TOKEN_CAP) estimated tokens (an
 * agent-led head group is never floor-protected, and a pathologically
 * oversized exchange is dropped, not kept); and the result is a pure
 * function of the inputs.
 */
export function trimHistory(
  history: ChatTurn[],
  opts: { budgetTokens: number; keepLastTurns?: number },
): ChatTurn[] {
  const keepLastTurns = opts.keepLastTurns ?? 2;
  if (history.length === 0) return [];
  const hardCap = Math.max(opts.budgetTokens, FLOOR_TOKEN_CAP);
  const exchanges = groupExchanges(history);
  const kept: ChatTurn[][] = [];
  let spent = 0;
  let floorUsed = 0;
  for (let i = exchanges.length - 1; i >= 0; i--) {
    const exchange = exchanges[i];
    const cost = exchange.reduce((sum, turn) => sum + estimateTokens(turn.text), 0);
    const userLed = exchange[0].role === "user";
    const fitsBudget = spent + cost <= opts.budgetTokens;
    const floorProtected = userLed && floorUsed < keepLastTurns && spent + cost <= hardCap;
    if (!fitsBudget && !floorProtected) break;
    kept.unshift(exchange);
    spent += cost;
    if (userLed) floorUsed++;
  }
  return kept.flat();
}

/**
 * Group oldest-first turns into user-led exchanges: one user turn plus every
 * agent turn that follows it before the next user turn. Agent turns arriving
 * before any user turn (an opening greeting) form their own head group.
 */
function groupExchanges(history: ChatTurn[]): ChatTurn[][] {
  const exchanges: ChatTurn[][] = [];
  for (const turn of history) {
    if (turn.role === "user" || exchanges.length === 0) exchanges.push([turn]);
    else exchanges[exchanges.length - 1].push(turn);
  }
  return exchanges;
}

/** Map wire turns to Vercel AI SDK core messages (wire "agent" -> SDK "assistant"). */
export function toCoreMessages(
  history: ChatTurn[],
): Array<{ role: "user" | "assistant"; content: string }> {
  return history.map((turn) =>
    turn.role === "agent"
      ? { role: "assistant" as const, content: turn.text }
      : { role: "user" as const, content: turn.text },
  );
}
```

</details>

## See also

- [`../reference/chat-contract.md`](../reference/chat-contract.md) — the wire shape this trims.
- [`../recipes/SCHEMA.md`](../recipes/SCHEMA.md) — `runtime_modes[<mode>].context_budget`, where the budget comes from.
- [`prompt-management.md`](prompt-management.md) — the system prompt this budget must leave room for.
- [`agent-blueprints/foundations/context-engineering.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/foundations/context-engineering.md) — the select/compress/prune/persist frame this doc operationalizes.
- [`agent-blueprints/primitives/memory/overview.md`](https://github.com/jagguvarma15/agent-blueprints/blob/main/primitives/memory/overview.md) — turn-count window plus long-term stores; this doc is the token-budget refinement of its WorkingMemory.
