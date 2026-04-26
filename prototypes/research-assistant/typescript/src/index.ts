import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { researchRouter } from "./api/research.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", researchRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`research-assistant running at http://localhost:${info.port}`);
});

export default app;
