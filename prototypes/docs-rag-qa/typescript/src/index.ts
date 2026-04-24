import { serve } from "@hono/node-server";
import { Hono } from "hono";
import { documentsRouter } from "./api/documents.js";
import { queryRouter } from "./api/query.js";

const app = new Hono();

app.get("/health", (c) => c.json({ status: "ok" }));
app.route("/", documentsRouter);
app.route("/", queryRouter);

const port = Number(process.env.PORT ?? 8000);

serve({ fetch: app.fetch, port }, (info) => {
  console.log(`docs-rag-qa running at http://localhost:${info.port}`);
});

export default app;
