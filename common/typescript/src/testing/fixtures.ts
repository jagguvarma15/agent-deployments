/**
 * Shared test utilities for agent-deployments prototypes.
 */

export interface MockLlmResponse {
  choices: Array<{
    message: { role: string; content: string; tool_calls?: unknown[] };
    finish_reason: string;
  }>;
  model: string;
  usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number };
}

/**
 * Create a mock LLM response object.
 */
export function mockLlmResponse(
  content = "Hello from mock LLM",
  options: {
    model?: string;
    finishReason?: string;
    toolCalls?: unknown[];
  } = {},
): MockLlmResponse {
  return {
    choices: [
      {
        message: {
          role: "assistant",
          content,
          tool_calls: options.toolCalls ?? [],
        },
        finish_reason: options.finishReason ?? "stop",
      },
    ],
    model: options.model ?? "mock-model",
    usage: {
      prompt_tokens: 10,
      completion_tokens: 20,
      total_tokens: 30,
    },
  };
}

/**
 * Create a mock LLM client that returns predefined responses.
 */
export function mockLlmClient(responses: string[] = ["Mock response"]) {
  let callCount = 0;

  return {
    chat: {
      completions: {
        create: async (): Promise<MockLlmResponse> => {
          const content = responses[callCount % responses.length]!;
          callCount++;
          return mockLlmResponse(content);
        },
      },
    },
  };
}
