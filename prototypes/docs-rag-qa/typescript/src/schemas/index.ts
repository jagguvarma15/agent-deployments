import { z } from "zod";

export const DocumentIngestRequest = z.object({
  content: z.string().min(1),
  title: z.string().min(1),
  metadata: z.record(z.unknown()).optional(),
});
export type DocumentIngestRequest = z.infer<typeof DocumentIngestRequest>;

export const DocumentIngestResponse = z.object({
  document_id: z.string(),
  chunk_count: z.number(),
  status: z.string(),
});
export type DocumentIngestResponse = z.infer<typeof DocumentIngestResponse>;

export const QueryRequest = z.object({
  question: z.string().min(1),
  top_k: z.number().default(5),
});
export type QueryRequest = z.infer<typeof QueryRequest>;

export const Citation = z.object({
  chunk_id: z.string(),
  document_title: z.string(),
  text: z.string(),
  score: z.number(),
});
export type Citation = z.infer<typeof Citation>;

export const QueryResponse = z.object({
  answer: z.string(),
  citations: z.array(Citation),
  trace_id: z.string(),
});
export type QueryResponse = z.infer<typeof QueryResponse>;
