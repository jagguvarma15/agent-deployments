import { z } from "zod";

const configSchema = z.object({
  appName: z.string().default("customer-support-triage"),
  appEnv: z.string().default("development"),
  logLevel: z.string().default("info"),

  anthropicApiKey: z.string().default(""),
  classifierModel: z.string().default("claude-haiku-4-5-20251001"),
  specialistModel: z.string().default("claude-sonnet-4-6-20250514"),

  escalationThreshold: z.coerce.number().default(0.7),

  databaseUrl: z
    .string()
    .default("postgresql://agent:agent@localhost:5432/agent_db"),
  redisUrl: z.string().default("redis://localhost:6379"),
  qdrantUrl: z.string().default("http://localhost:6333"),

  jwtSecret: z.string().default("change-me-in-production"),

  langfusePublicKey: z.string().default("pk-lf-local"),
  langfuseSecretKey: z.string().default("sk-lf-local"),
  langfuseHost: z.string().default("http://localhost:3000"),
});

export const config = configSchema.parse({
  appName: process.env.APP_NAME,
  appEnv: process.env.APP_ENV,
  logLevel: process.env.LOG_LEVEL,
  anthropicApiKey: process.env.ANTHROPIC_API_KEY,
  classifierModel: process.env.CLASSIFIER_MODEL,
  specialistModel: process.env.SPECIALIST_MODEL,
  escalationThreshold: process.env.ESCALATION_THRESHOLD,
  databaseUrl: process.env.DATABASE_URL,
  redisUrl: process.env.REDIS_URL,
  qdrantUrl: process.env.QDRANT_URL,
  jwtSecret: process.env.JWT_SECRET,
  langfusePublicKey: process.env.LANGFUSE_PUBLIC_KEY,
  langfuseSecretKey: process.env.LANGFUSE_SECRET_KEY,
  langfuseHost: process.env.LANGFUSE_HOST,
});

export type Config = z.infer<typeof configSchema>;
