/**
 * Triage route handler.
 */

import { Hono } from "hono";
import { classifyIntent } from "../agent/classifier.js";
import { runSpecialist } from "../agent/specialists.js";
import { config } from "../config.js";
import { TriageRequest } from "../schemas/index.js";

export const triageRouter = new Hono();

triageRouter.post("/triage", async (c) => {
  const body = await c.req.json();
  const parsed = TriageRequest.safeParse(body);

  if (!parsed.success) {
    return c.json({ error: "Invalid request", details: parsed.error.issues }, 400);
  }

  const { message, user_id } = parsed.data;
  const traceId = crypto.randomUUID();
  const conversationId = crypto.randomUUID();

  // Classify intent
  const classification = await classifyIntent(message);

  // Check escalation threshold
  if (classification.confidence < config.escalationThreshold) {
    return c.json({
      conversation_id: conversationId,
      intent: classification.intent,
      specialist_response: "Escalated to human agent due to low classification confidence.",
      escalated: true,
      trace_id: traceId,
    });
  }

  // Route to specialist
  const { text, toolCalls } = await runSpecialist(classification.intent, message);

  return c.json({
    conversation_id: conversationId,
    intent: classification.intent,
    specialist_response: text,
    escalated: false,
    trace_id: traceId,
  });
});
