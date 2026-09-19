# The `/chat` contract

The default frontend (`frontend.minimal-chat`, attached to every recipe that
doesn't ship its own UI) talks to the generated backend over one small,
**non-streaming JSON** endpoint. Any recipe whose backend is reached by the chat
UI must satisfy it — the scaffold's generator is instructed to expose it, and a
generation-time backstop (`assert_chat_endpoint`) flags a missing route.

## Request

```
POST /chat
Content-Type: application/json

{ "message": "<user text>", "history": [ { "role": "user|agent", "text": "..." } ] }
```

- `message` (required) — the user's latest turn.
- `history` (recommended) — prior turns, oldest first. Both default UIs send it;
  backends must accept it, tolerate its absence, and trim it deterministically to
  the recipe's context budget before the model call — see
  [context management](../cross-cutting/context-management.md).

## Response

```
200 OK
Content-Type: application/json

{ "reply": "<agent text>" }
```

- `reply` (required) — the agent's answer as a plain string. The UI also accepts
  `answer` / `message` / `output` as fallback keys, but **`reply` is canonical** —
  emit it.
- Non-streaming. Do **not** use Server-Sent Events or chunked token streaming for
  `/chat`; return the full reply in one JSON body.

## Adapting an existing route

If a recipe's backend already exposes its logic under a different path (e.g.
`/support`, `/ask`), add a thin `POST /chat` adapter that maps `{message}` to that
handler and wraps its output as `{"reply": ...}`. Do not rename the native route —
add `/chat` alongside it.

## Multi-turn

Clients cap what they send as a courtesy, but the server-side trim is the
authoritative bound — the wire accepts any history length. When passing turns to
an SDK, map the wire role `agent` to the SDK's `assistant`; the wire never carries
`assistant` or `system` roles.

## System prompt

When the scaffold provides an **Agent role** (from the "describe your agent" step
or the recipe's `agent_role` frontmatter), that text is the agent's system prompt:
wire it into the model call behind `/chat` so the agent answers in character.
