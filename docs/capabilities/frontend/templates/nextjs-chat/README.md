# nextjs-chat template

The agent-scaffold capability `frontend.nextjs-chat` copies this directory verbatim into the generated project under `frontend/`. The result is a runnable Next.js 14 chat shell that speaks the canonical `/chat` contract to the project's agent service through a same-origin adapter proxy.

## Run locally

```bash
cd frontend
pnpm install         # or `npm install` / `yarn install`
pnpm dev             # http://localhost:3000
```

The chat UI calls `POST /api/agent` (a thin same-origin proxy in `app/api/agent/route.ts`) which forwards to `${NEXT_PUBLIC_AGENT_URL}/chat`. Override the backend URL in `.env.local`:

```
NEXT_PUBLIC_AGENT_URL=http://localhost:8000
```

## Required backend contract

The backend exposes `POST /chat` per the canonical chat contract (`docs/reference/chat-contract.md`):

- Accept `POST` with JSON body `{ "message": "<text>", "history": [{ "role": "user" | "agent", "text": "<text>" }] }` (history optional, oldest first)
- Return non-streaming JSON `{ "reply": "<text>" }` — no SSE, no chunked token streaming

The browser side keeps the Vercel AI SDK ergonomics: `useChat({ api: "/api/agent", streamProtocol: "text" })`. The `/api/agent` proxy adapts between the two shapes — it extracts the latest user message plus prior turns from the SDK's `{messages}` body, posts the contract shape to `/chat`, and returns the `reply` as plain text, which the SDK accepts as one complete assistant message.

## Customizing per recipe

Generated projects typically extend this template in three places:

1. **`app/page.tsx`** — change the header copy or add a sidebar.
2. **`components/Message.tsx`** — render tool-call bubbles or domain-specific message types.
3. **Add `app/branding.ts`** (not shipped here; create it in the generated project) — central place to pin the agent name and theme tokens; import from `Chat.tsx` and `page.tsx`.

Capability template copy NEVER overwrites a file the generator emits. Any of the three files above can be replaced verbatim in the generated project without conflicting with this template.

## Smoke-tested with

- `pnpm install` (lockfile not shipped; the install step solves it from `package.json`)
- `pnpm build` exits 0 with no type errors against the pinned versions in `package.json`
- Manual: `pnpm dev` and visit `http://localhost:3000`; with no backend running you should see "agent error" in the banner — wire the backend and replies render

## Why these choices

- **Next.js 14 App Router**: first-class route handlers for the adapter proxy; native Vercel AI SDK support.
- **Edge runtime for `/api/agent`**: cheaper, faster cold starts; the proxy is stateless.
- **Tailwind for styling**: no design-system commitment; trivial to swap out.
- **No external state management**: the AI SDK's `useChat` covers the only state the UI needs.
