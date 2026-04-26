import { Hono } from "hono";
import { ResearchRequest } from "../schemas/index.js";

export const researchRouter = new Hono();

const results: Map<string, { status: string; steps: number }> = new Map();

researchRouter.post("/research", async (c) => {
  const body = await c.req.json();
  const parsed = ResearchRequest.safeParse(body);

  if (!parsed.success) {
    return c.json(
      { error: "Invalid request", details: parsed.error.issues },
      400,
    );
  }

  const researchId = crypto.randomUUID();
  const traceId = crypto.randomUUID();

  const steps = [
    {
      step: 1,
      action: "search",
      content: `Searching for: ${parsed.data.question}`,
    },
    { step: 2, action: "analyze", content: "Analyzing search results" },
    { step: 3, action: "synthesize", content: "Synthesizing findings" },
  ];

  const sources = [
    {
      title: "Example Source",
      url: "https://example.com",
      excerpt: "Relevant information found here.",
    },
  ];

  results.set(researchId, { status: "completed", steps: steps.length });

  return c.json({
    id: researchId,
    question: parsed.data.question,
    steps,
    answer: `Based on research, here is the answer to: ${parsed.data.question}`,
    sources,
    trace_id: traceId,
  });
});

researchRouter.get("/research/:researchId/status", (c) => {
  const researchId = c.req.param("researchId");
  const info = results.get(researchId) ?? { status: "not_found", steps: 0 };

  return c.json({
    id: researchId,
    status: info.status,
    steps_completed: info.steps,
  });
});
