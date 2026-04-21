/**
 * Hono entrypoint for the prototype.
 */

import { serve } from "@hono/node-server";
import { Hono } from "hono";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`Server running at http://localhost:${info.port}`);
});

export default app;
