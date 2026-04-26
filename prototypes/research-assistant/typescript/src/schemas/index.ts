import { z } from "zod";

export const ResearchRequest = z.object({
  question: z.string().min(1),
  max_steps: z.number().default(5),
});
export type ResearchRequest = z.infer<typeof ResearchRequest>;

export const Source = z.object({
  title: z.string(),
  url: z.string(),
  excerpt: z.string(),
});
export type Source = z.infer<typeof Source>;

export const ResearchStep = z.object({
  step: z.number(),
  action: z.string(),
  content: z.string(),
});
export type ResearchStep = z.infer<typeof ResearchStep>;

export const ResearchResult = z.object({
  id: z.string(),
  question: z.string(),
  steps: z.array(ResearchStep),
  answer: z.string(),
  sources: z.array(Source),
  trace_id: z.string(),
});
export type ResearchResult = z.infer<typeof ResearchResult>;

export const ResearchStatus = z.object({
  id: z.string(),
  status: z.string(),
  steps_completed: z.number(),
});
export type ResearchStatus = z.infer<typeof ResearchStatus>;
