import { z } from "zod";

export const Intent = z.enum(["billing", "technical", "account", "general"]);
export type Intent = z.infer<typeof Intent>;

export const ClassificationResult = z.object({
  intent: Intent,
  confidence: z.number().min(0).max(1),
  reasoning: z.string(),
});
export type ClassificationResult = z.infer<typeof ClassificationResult>;

export const TriageRequest = z.object({
  message: z.string().min(1),
  user_id: z.string().min(1),
});
export type TriageRequest = z.infer<typeof TriageRequest>;

export const TriageResponse = z.object({
  conversation_id: z.string(),
  intent: z.string(),
  specialist_response: z.string(),
  escalated: z.boolean(),
  trace_id: z.string(),
});
export type TriageResponse = z.infer<typeof TriageResponse>;
