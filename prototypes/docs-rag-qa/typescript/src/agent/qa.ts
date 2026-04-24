/**
 * QA agent using Vercel AI SDK with retrieval tool.
 */

import { anthropic } from "@ai-sdk/anthropic";
import { generateText, tool } from "ai";
import { z } from "zod";
import { config } from "../config.js";
import { searchSimilar } from "../tools/retriever.js";

const QA_SYSTEM_PROMPT = `You are a document Q&A assistant.
Given a user question, search the knowledge base for relevant content,
then provide a clear, accurate answer with citations to the source documents.
Always cite which document your answer comes from.`;

export async function answerQuestion(
  question: string,
  topK = 5,
): Promise<{
  text: string;
  toolCalls: Array<{ toolName: string; args: Record<string, unknown> }>;
}> {
  const qaTools = {
    search_knowledge_base: tool({
      description: "Search the document knowledge base for relevant chunks",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => searchSimilar(query, topK),
    }),
  };

  const result = await generateText({
    model: anthropic(config.qaModel),
    system: QA_SYSTEM_PROMPT,
    prompt: question,
    tools: qaTools,
    maxSteps: 3,
  });

  const toolCalls = result.steps
    .flatMap((s) => s.toolCalls)
    .map((tc: { toolName: string; args: unknown }) => ({
      toolName: tc.toolName,
      args: tc.args as Record<string, unknown>,
    }));

  return { text: result.text, toolCalls };
}
