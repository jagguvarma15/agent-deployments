/**
 * Application configuration via environment variables.
 */

import { z } from "zod";

const configSchema = z.object({
  appName: z.string().default("prototype-name"),
  appEnv: z.string().default("development"),
  logLevel: z.string().default("info"),

  // LLM
  anthropicApiKey: z.string().default(""),

  // Database
  databaseUrl: z.string().default("postgresql://agent:agent@localhost:5432/agent_db"),

  // Redis
  redisUrl: z.string().default("redis://localhost:6379"),

  // Auth
  jwtSecret: z.string().default("change-me-in-production"),

  // Langfuse
  langfusePublicKey: z.string().default("pk-lf-local"),
  langfuseSecretKey: z.string().default("sk-lf-local"),
  langfuseHost: z.string().default("http://localhost:3000"),
});

export const config = configSchema.parse({
  appName: process.env.APP_NAME,
  appEnv: process.env.APP_ENV,
  logLevel: process.env.LOG_LEVEL,
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  databaseUrl: process.env.DATABASE_URL,
  redisUrl: process.env.REDIS_URL,
  jwtSecret: process.env.JWT_SECRET,
  langfusePublicKey: process.env.LANGFUSE_PUBLIC_KEY,
  langfuseSecretKey: process.env.LANGFUSE_SECRET_KEY,
  langfuseHost: process.env.LANGFUSE_HOST,
});

export type Config = z.infer<typeof configSchema>;
