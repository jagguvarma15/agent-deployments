import { anthropic } from "@ai-sdk/anthropic";
import { generateText, tool } from "ai";
import { z } from "zod";
import { config } from "../config.js";
import { webSearch } from "../tools/web-search.js";

const SYSTEM_PROMPT = `You are a research assistant. Given a question, search for information, \
analyze results, and provide a comprehensive answer with sources.`;

export async function runResearch(
  question: string,
  maxSteps = 5,
): Promise<{
  answer: string;
  steps: Array<{ step: number; action: string; content: string }>;
}> {
  const researchTools = {
    search_web: tool({
      description: "Search the web for relevant information",
      parameters: z.object({ query: z.string() }),
      execute: async ({ query }) => webSearch(query),
    }),
  };

  const result = await generateText({
    model: anthropic(config.researchModel),
    system: SYSTEM_PROMPT,
    prompt: question,
    tools: researchTools,
    maxSteps,
  });

  const steps: Array<{ step: number; action: string; content: string }> =
    result.steps.flatMap((s, i) =>
      s.toolCalls.map((tc) => ({
        step: i + 1,
        action: tc.toolName,
        content: `${tc.toolName}: ${JSON.stringify(tc.args)}`,
      })),
    );

  if (steps.length === 0) {
    steps.push({
      step: 1,
      action: "search",
      content: `Researched: ${question}`,
    });
  }

  return { answer: result.text, steps };
}
