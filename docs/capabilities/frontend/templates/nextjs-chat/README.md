# nextjs-chat template

The agent-scaffold capability `frontend.nextjs-chat` copies this directory verbatim into the generated project under `frontend/`. The result is a runnable Next.js 14 chat shell wired to consume Vercel AI SDK streaming responses from the project's agent service.

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

The chat shell speaks the Vercel AI SDK protocol via `useChat({ api: "/api/agent" })`. The backend `/chat` endpoint should:

- Accept `POST` with JSON body `{ messages: { role, content }[] }`
- Return a streaming response in the AI SDK Data Stream Protocol (`text/plain` or `text/event-stream`)

Most LangGraph / Pydantic AI / Vercel AI SDK backends ship a `/chat` endpoint that already matches this shape. If not, adapt your endpoint to stream `0:"chunk"\n` framed lines.

## Customizing per recipe

Generated projects typically extend this template in three places:

1. **`app/page.tsx`** — change the header copy or add a sidebar.
2. **`components/Message.tsx`** — render tool-call bubbles or domain-specific message types.
3. **Add `app/branding.ts`** (not shipped here; create it in the generated project) — central place to pin the agent name and theme tokens; import from `Chat.tsx` and `page.tsx`.

Capability template copy NEVER overwrites a file the generator emits. Any of the three files above can be replaced verbatim in the generated project without conflicting with this template.

## Smoke-tested with

- `pnpm install` (lockfile not shipped; the install step solves it from `package.json`)
- `pnpm build` exits 0 with no type errors against the pinned versions in `package.json`
- Manual: `pnpm dev` and visit `http://localhost:3000`; with no backend running you should see "agent error 502" — wire the backend and the chat starts streaming

## Why these choices

- **Next.js 14 App Router**: native streaming-response support; matches the Vercel AI SDK's expected shape.
- **Edge runtime for `/api/agent`**: cheaper, faster cold starts; the proxy is stateless.
- **Tailwind for styling**: no design-system commitment; trivial to swap out.
- **No external state management**: the AI SDK's `useChat` covers the only state the UI needs.
