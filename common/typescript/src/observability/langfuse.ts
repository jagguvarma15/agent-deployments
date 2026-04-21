/**
 * Langfuse client wrapper and trace utilities.
 *
 * Note: This is a lightweight wrapper. The actual Langfuse SDK should be
 * installed in each prototype that needs it. This module provides the
 * configuration shape and a traced() helper pattern.
 */

export interface LangfuseConfig {
  publicKey: string;
  secretKey: string;
  host?: string;
}

interface TraceSpan {
  name: string;
  startTime: number;
  endTime?: number;
  metadata?: Record<string, unknown>;
  status?: "ok" | "error";
  error?: string;
}

let _config: LangfuseConfig | null = null;

/**
 * Initialize the Langfuse client configuration.
 */
export function createLangfuseClient(config: LangfuseConfig): LangfuseConfig {
  _config = config;
  return _config;
}

/**
 * Decorator-style wrapper that traces a function execution.
 *
 * Usage:
 *   const result = await traced("my-operation", async () => {
 *     return doSomething();
 *   });
 */
export async function traced<T>(
  name: string,
  fn: () => Promise<T>,
  metadata?: Record<string, unknown>,
): Promise<T> {
  const span: TraceSpan = {
    name,
    startTime: Date.now(),
    metadata,
  };

  try {
    const result = await fn();
    span.endTime = Date.now();
    span.status = "ok";
    return result;
  } catch (error) {
    span.endTime = Date.now();
    span.status = "error";
    span.error = error instanceof Error ? error.message : String(error);
    throw error;
  }
}
