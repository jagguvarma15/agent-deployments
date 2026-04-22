# Stack Swaps — customer-support-triage

## Single-file swaps

| Default | Alternative | What to change |
|---------|-------------|----------------|
| Claude Haiku 4.5 (classifier) | GPT-4.1-mini | Change `CLASSIFIER_MODEL` in settings |
| Claude Sonnet 4.6 (specialists) | GPT-4.1 | Change `SPECIALIST_MODEL` in settings |

## Multi-file swaps

| Default | Alternative | Files affected |
|---------|-------------|---------------|
| Qdrant (KB search) | pgvector | `tools/kb.py`, `docker-compose.yml` (remove qdrant service) |
| Langfuse | LangSmith | `observability` imports in agent modules, docker-compose (remove langfuse services) |
| Mock Stripe MCP | Real Stripe MCP server | `tools/stripe.py` — point to real MCP server URL, add `STRIPE_API_KEY` to `.env` |

## Architectural swaps

| Default | Alternative | Impact |
|---------|-------------|--------|
| Pydantic AI (Python) | LangGraph | Rewrite classifier as a graph node; changes state management approach |
| Mastra (TypeScript) | Vercel AI SDK (raw) | Lose built-in handoff; must implement routing logic manually |
