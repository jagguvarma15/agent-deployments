/**
 * Query route handler.
 */

import { Hono } from "hono";
import { answerQuestion } from "../agent/qa.js";
import { QueryRequest } from "../schemas/index.js";

export const queryRouter = new Hono();

queryRouter.post("/query", async (c) => {
  const body = await c.req.json();
  const parsed = QueryRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const { question, top_k } = parsed.data;
  const traceId = crypto.randomUUID();

  const { text } = await answerQuestion(question, top_k);

  return c.json({
    answer: text,
    citations: [],
    trace_id: traceId,
  });
});
