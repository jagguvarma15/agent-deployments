# Directory map

One-screen tour for AI tools and new contributors. Companion to [`llms.txt`](llms.txt) and [`agents.md`](agents.md).

```
agent-deployments/
├── catalog.yaml              # Auto-generated index — single source of truth for consumers.
├── MANIFEST_SCHEMA.md        # catalog.yaml schema.
├── llms.txt                  # AI-tool discovery (llmstxt.org spec).
├── agents.md                 # Programmatic-consumption guide.
├── STRUCTURE.md              # This file.
│
├── docs/
│   ├── recipes/              # 11 agent blueprints. Each declares pattern + primitives
│   │                         #   + modifiers + capabilities in frontmatter.
│   │   └── SCHEMA.md         #   Recipe frontmatter contract.
│   ├── capabilities/         # Infrastructure capability docs, one dir per kind:
│   │   ├── vector_db/        #   {qdrant, chroma, pgvector, ...}
│   │   ├── cache/            #   {redis, ...}
│   │   ├── relational/       #   {postgres, ...}
│   │   ├── queue/            #   {kafka, redis-streams, ...}
│   │   ├── obs/              #   {langfuse, langsmith, ...}
│   │   ├── eval/             #   {promptfoo, deepeval, ...}
│   │   ├── frontend/         #   {nextjs-chat, streamlit, ...}
│   │   ├── host/             #   {vercel, fly, ...}
│   │   ├── mcp/              #   {tavily, postgres, ...}            (2026-SOTA)
│   │   ├── sandbox/          #   {e2b, ...}                          (2026-SOTA)
│   │   ├── durable/          #   {temporal, ...}                     (2026-SOTA)
│   │   ├── memory_store/     #   {zep, ...}                          (2026-SOTA)
│   │   ├── guardrail/        #   {llama-guard, ...}                  (2026-SOTA)
│   │   ├── embedding/        #   {openai, ...}                       (2026-SOTA)
│   │   ├── live_data/        #   {tavily, ...}                       (2026-SOTA)
│   │   └── rerank/           #   {cohere, ...}                       (2026-SOTA)
│   ├── ports/                # Abstract port contracts adapters bind to (model,
│   │                         #   tools, memory, vector_db, eval, framework, …).
│   ├── frameworks/           # LangGraph, Pydantic AI, CrewAI, Vercel AI SDK, …
│   ├── stack/                # FastAPI, Hono, Postgres, Redis, Qdrant, Langfuse, …
│   ├── cross-cutting/        # Auth, logging, observability, rate limiting, …
│   ├── getting-started/      # One-screen-per-service first-run remediation.
│   ├── reference/            # Dockerfile/compose/CI templates.
│   └── playbook/             # Design guides + production checklist.
│
├── reference/
│   └── blueprints/
│       └── patterns-catalog.yaml  # SHA-pinned copy of upstream agent-blueprints'
│                                  #   machine-readable index (embedded into catalog.yaml).
│                                  #   The only blueprints artifact committed here; doc
│                                  #   bodies are referenced by GitHub URL, not vendored.
│
└── scripts/
    ├── generate_catalog.py   # Builds catalog.yaml from this repo + the reference catalog.
    └── _seed_aliases.yaml    # Prose-token → doc path map; baked into catalog.aliases.
```

## Three orthogonal decisions

Designing an agent is three picks, in order. catalog.yaml has the canonical id sets for each:

1. **Pattern** — flow shape. `catalog.patterns[]`. Pick one.
2. **Primitives** — building blocks. `catalog.primitives[]`. Pick any.
3. **Modifiers** — transforms. `catalog.modifiers[]`. Pick any.

Each recipe declares its three picks in frontmatter (`agent_pattern:`, `primitives:`, `modifiers:`). See [`docs/recipes/SCHEMA.md`](docs/recipes/SCHEMA.md).

## How content flows

```
agent-blueprints (release)
        ↓ release-driven sync (fetch patterns-catalog.yaml)
reference/blueprints/patterns-catalog.yaml  +  docs/{recipes,capabilities,ports,frameworks,stack,cross-cutting}/
        ↓ scripts/generate_catalog.py
catalog.yaml
        ↓ HTTP fetch (one URL)
agent-scaffold (CLI)
```

catalog.yaml is the contract; nothing else in this repo is required reading for consumers.
