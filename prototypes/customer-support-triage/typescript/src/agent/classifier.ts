/**
 * Intent classifier using Vercel AI SDK with structured output.
 */

import { generateObject } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { config } from "../config.js";
import { ClassificationResult } from "../schemas/index.js";

const CLASSIFIER_SYSTEM_PROMPT = `You are a customer support intent classifier.
Given a customer message, classify it into exactly one of these intents:
- billing: payment issues, subscription changes, invoices, charges, refunds
- technical: bugs, errors, API issues, integration problems, performance
- account: password resets, profile updates, access issues, account settings
- general: everything else, general questions, feedback, feature requests

Return the intent, your confidence (0.0 to 1.0), and brief reasoning.`;

export async function classifyIntent(
  message: string,
): Promise<{ intent: string; confidence: number; reasoning: string }> {
  const result = await generateObject({
    model: anthropic(config.classifierModel),
    schema: ClassificationResult,
    system: CLASSIFIER_SYSTEM_PROMPT,
    prompt: message,
  });

  return result.object;
}
