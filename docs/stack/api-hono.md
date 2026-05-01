# Stack pick: Hono

**Choice:** Hono 4.6 on Node.js runtime (Cloudflare Workers-compatible)
**Used for:** TypeScript API layer for all agent prototypes

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Express | No native TypeScript, no edge runtime support, middleware API is dated |
| Fastify | Strong alternative but heavier; Hono's minimal API pairs better with Mastra |
| Next.js API routes | Ties you to Vercel/Next.js; overkill for a standalone agent API |
| tRPC | Great for full-stack TS apps, but agent APIs are usually consumed by non-TS clients too |

Hono was chosen for its minimal footprint, fast performance, native TypeScript, and compatibility with both Node.js and edge runtimes.

## Local setup

Hono runs inside the `app` service in the project's `docker-compose.yml` (see [Docker Compose template](../reference/docker-compose-template.md)), or standalone:

```bash
pnpm install
pnpm run dev   # typically runs tsx with --watch
```

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| Port | 8000 | Set via `PORT` env var |
| Runtime | Node.js (`@hono/node-server`) | Can deploy to Cloudflare Workers, Deno, or Bun without code changes |

## Integration pattern

### App entrypoint (`src/index.ts`)

```typescript
import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { queryRouter } from "./api/query.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", queryRouter);

const port = Number(process.env.PORT ?? 8000);
serve({ fetch: app.fetch, port }, (info) => {
  console.log(`Running at http://localhost:${info.port}`);
});

export default app;
```

### Route handler pattern

```typescript
import { Hono } from "hono";
import { zValidator } from "@hono/zod-validator";
import { QueryRequestSchema } from "../schemas/index.js";

const router = new Hono();

router.post("/query", zValidator("json", QueryRequestSchema), async (c) => {
  const { question, topK } = c.req.valid("json");
  const { text, toolCalls } = await answerQuestion(question, topK);
  return c.json({ answer: text, citations: toolCalls, traceId: crypto.randomUUID() });
});

export { router as queryRouter };
```

### Adding cross-cutting concerns

```typescript
import { verifyToken } from "@agent-deployments/common";
import { buildRateLimiter } from "@agent-deployments/common";

// Auth middleware
app.use("/query/*", async (c, next) => {
  const token = c.req.header("Authorization")?.replace("Bearer ", "");
  if (!token) return c.json({ error: "Unauthorized" }, 401);
  const payload = await verifyToken(token, config.jwtSecret);
  c.set("userId", payload.sub);
  await next();
});

// Rate limiting middleware
const checkLimit = buildRateLimiter({ redisUrl: config.redisUrl, maxRequests: 30, windowSeconds: 60 });
app.use("/query/*", async (c, next) => {
  const key = c.get("userId") ?? "anon";
  if (!checkLimit(key).allowed) return c.json({ error: "Rate limit exceeded" }, 429);
  await next();
});
```

## Where used in repo

Every TypeScript blueprint uses Hono as its API layer. See the `src/index.ts` entry in each blueprint's Key files table.

## Swapping to Fastify

1. Replace `Hono` with `Fastify`, `c.json()` with `reply.send()`.
2. Replace Hono middleware with Fastify plugins/hooks.
3. Replace `@hono/zod-validator` with `fastify-type-provider-zod`.
4. Adjust `serve()` to Fastify's `listen()`.

This is a **multi-file swap** (index.ts + all route files + middleware).
