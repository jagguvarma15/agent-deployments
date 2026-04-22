/**
 * Specialist agents for each intent category.
 */

import { generateText, tool } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { z } from "zod";
import { config } from "../config.js";
import { stripeLookup } from "../tools/stripe.js";
import { kbSearch } from "../tools/kb.js";

const SPECIALIST_PROMPTS: Record<string, string> = {
  billing: `You are a billing support specialist. Help customers with payment issues,
subscription changes, invoices, and charges. You have access to the Stripe tool to look up
billing information. Be helpful, concise, and professional.`,
  technical: `You are a technical support specialist. Help customers with bugs, errors,
API issues, and integration problems. You have access to a knowledge base search tool.
Provide clear, actionable guidance.`,
  account: `You are an account support specialist. Help customers with password resets,
profile updates, and account settings. You have access to a knowledge base search tool.
Guide them step by step.`,
  general: `You are a general support specialist. Help customers with general questions,
feedback, and feature requests. Be friendly and helpful.`,
};

const billingTools = {
  lookup_billing: tool({
    description: "Look up billing information for a customer using Stripe",
    parameters: z.object({ query: z.string() }),
    execute: async ({ query }) => stripeLookup(query),
  }),
};

const kbTools = {
  search_knowledge_base: tool({
    description: "Search the knowledge base for relevant articles",
    parameters: z.object({ query: z.string() }),
    execute: async ({ query }) => kbSearch(query),
  }),
};

const SPECIALIST_TOOLS: Record<string, Record<string, ReturnType<typeof tool>>> = {
  billing: billingTools,
  technical: kbTools,
  account: kbTools,
  general: {},
};

export async function runSpecialist(
  intent: string,
  message: string,
): Promise<{ text: string; toolCalls: Array<{ toolName: string; args: Record<string, unknown> }> }> {
  const systemPrompt = SPECIALIST_PROMPTS[intent] ?? SPECIALIST_PROMPTS.general;
  const tools = SPECIALIST_TOOLS[intent] ?? {};

  const result = await generateText({
    model: anthropic(config.specialistModel),
    system: systemPrompt,
    prompt: message,
    tools,
    maxSteps: 3,
  });

  const toolCalls = result.steps
    .flatMap((s) => s.toolCalls)
    .map((tc) => ({ toolName: tc.toolName, args: tc.args as Record<string, unknown> }));

  return { text: result.text, toolCalls };
}
