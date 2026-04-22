import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { triageRouter } from "./api/triage.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", triageRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`customer-support-triage running at http://localhost:${info.port}`);
});

export default app;
