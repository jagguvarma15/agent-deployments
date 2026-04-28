# Pattern: RAG (Retrieval-Augmented Generation)

**One-liner:** Ground LLM answers in retrieved documents so the model answers from your data, not its training set.

## When to use

- User asks questions that should be answered from a specific corpus (docs, KB articles, policies).
- You need citations or source attribution in answers.
- The knowledge base changes over time and can't be baked into prompts.
- You want to reduce hallucination by constraining the model to retrieved context.

## When NOT to use

- The answer space is small enough to fit in the system prompt (use direct prompting).
- You need the agent to take *actions*, not just answer questions (use ReAct or Routing).
- The corpus is unstructured and doesn't chunk well (consider summarization pipelines first).

## Core flow

```
User question
    |
    v
  [Embed query] ──> [Vector search] ──> top-K chunks
    |                                        |
    v                                        v
  [Build prompt]  <──────────────────  [Retrieved context]
    |
    v
  [LLM generates answer grounded in context]
    |
    v
  Answer + citations
```

### Variants

- **Naive RAG:** Embed > retrieve > generate. Simple, works for most cases.
- **RAG + reranker:** Add a cross-encoder reranker after retrieval to improve precision.
- **Agentic RAG:** The LLM decides *when* and *what* to retrieve (retrieval as a tool call). This is what the `docs-rag-qa` prototype implements.
- **Multi-step RAG:** Decompose complex questions, retrieve per sub-question, synthesize.

## Key components

- **Chunker:** Splits documents into retrieval-sized pieces. Sentence-boundary splitting with overlap is the baseline. Typical chunk size: 300-800 characters.
- **Embedder:** Converts text to vectors. In this repo, Qdrant handles storage; embedding is done by the Qdrant client or a dedicated model.
- **Retriever:** Searches the vector store for chunks similar to the query. Returns top-K with relevance scores.
- **Generator:** The LLM that synthesizes an answer from the retrieved chunks. Gets the chunks injected into its prompt or via tool call results.
- **Citation extractor:** Maps answer spans back to source documents for attribution.

## Common pitfalls

- **Chunks too large:** The model ignores the middle of long contexts. Keep chunks focused.
- **Chunks too small:** Loss of surrounding context makes chunks meaningless. Use overlap.
- **No relevance threshold:** Returning irrelevant chunks harms answer quality. Filter by score.
- **Stuffing all chunks into one prompt:** With many results, use map-reduce or iterative refinement instead.
- **Ignoring metadata:** Filtering by document type, date, or source before vector search dramatically improves precision.
- **Not evaluating retrieval separately:** Measure retrieval recall/precision independently from generation quality. RAGAS is purpose-built for this.

## Framework fit

| Framework | Native support | Notes |
|-----------|----------------|-------|
| LangGraph | Built-in retriever nodes, checkpointing for multi-step RAG | Best for complex RAG with state management |
| Pydantic AI | Tool-based retrieval, type-safe citation schemas | Clean DX for simple agentic RAG |
| Mastra | Built-in RAG primitives, vector store integrations | TS-native, batteries included |
| Vercel AI SDK | Tool-based retrieval via `tool()` | Lightweight, good for simple RAG |
| CrewAI | Possible but not idiomatic | Better suited for multi-agent patterns |

## Evaluation metrics

RAG has dedicated metrics beyond general agent eval:

| Metric | What it measures | Tool |
|--------|-----------------|------|
| Context recall | Did retrieval find the right chunks? | RAGAS |
| Context precision | Are retrieved chunks relevant (not noise)? | RAGAS |
| Faithfulness | Is the answer grounded in retrieved context (not hallucinated)? | RAGAS |
| Answer relevancy | Does the answer address the question? | RAGAS / DeepEval |
| Answer correctness | Is the answer factually correct vs. gold standard? | DeepEval |

## Reference implementations

- [recipes/docs-rag-qa.md](../recipes/docs-rag-qa.md) -- Agentic RAG with Pydantic AI (Py) and Vercel AI SDK (TS)
