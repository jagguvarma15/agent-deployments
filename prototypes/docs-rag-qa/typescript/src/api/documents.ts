/**
 * Document ingestion route handler.
 */

import { Hono } from "hono";
import { DocumentIngestRequest } from "../schemas/index.js";
import { chunkDocument } from "../tools/chunker.js";
import { storeChunks } from "../tools/retriever.js";

export const documentsRouter = new Hono();

documentsRouter.post("/documents", async (c) => {
  const body = await c.req.json();
  const parsed = DocumentIngestRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const { content, title } = parsed.data;
  const documentId = crypto.randomUUID();
  const chunks = chunkDocument(content);

  storeChunks(documentId, title, chunks);

  return c.json({
    document_id: documentId,
    chunk_count: chunks.length,
    status: "ingested",
  });
});
