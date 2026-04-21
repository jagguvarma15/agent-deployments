/**
 * Structured logging using pino.
 */

import pino from "pino";

export interface LoggerConfig {
  serviceName: string;
  env?: string;
  level?: string;
}

/**
 * Create a configured pino logger instance.
 */
export function createLogger(config: LoggerConfig): pino.Logger {
  const { serviceName, env = "development", level = "info" } = config;

  const transport =
    env === "development"
      ? {
          target: "pino/file",
          options: { destination: 1 }, // stdout
        }
      : undefined;

  return pino({
    name: serviceName,
    level,
    transport,
    base: {
      service: serviceName,
      env,
    },
    timestamp: pino.stdTimeFunctions.isoTime,
  });
}
