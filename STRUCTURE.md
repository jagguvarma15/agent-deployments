# Directory map

One-screen tour for AI tools and new contributors. Companion to [`llms.txt`](llms.txt) and [`agents.md`](agents.md).

```
agent-deployments/
├── catalog.yaml              # Auto-generated index — single source of truth for consumers.
├── MANIFEST_SCHEMA.md        # catalog.yaml schema.
├── llms.txt                  # AI-tool discovery (llmstxt.org spec).
├── agents.md                 # Programmatic-consumption guide.
├── STRUCTURE.md              # This file.
├── vendir.yml                # Pinned upstream blueprints declaration.
├── vendir.lock.yml           # Resolved upstream SHA.
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
│   ├── frameworks/           # LangGraph, Pydantic AI, CrewAI, Vercel AI SDK, …
│   ├── stack/                # FastAPI, Hono, Postgres, Redis, Qdrant, Langfuse, …
│   ├── cross-cutting/        # Auth, logging, observability, rate limiting, …
│   ├── getting-started/      # One-screen-per-service first-run remediation.
│   ├── reference/            # Dockerfile/compose/CI templates.
│   └── playbook/             # Design guides + production checklist.
│
├── vendored/
│   └── blueprints/           # SHA-pinned snapshot of agent-blueprints. Never edit.
│       ├── patterns/         # 14 flow shapes (agent + workflow, via category field).
│       ├── workflows/        # Legacy view; will move into patterns/ in upstream v3.
│       ├── primitives/       # 4 building blocks: memory, tool_use, skills, sub_agents.
│       ├── modifiers/        # 2 transforms: guardrails, human_in_the_loop.
│       ├── foundations/      # Terminology, anatomy, choosing a pattern, …
│       ├── composition/      # How patterns + primitives + modifiers combine.
│       ├── meta/             # Contributing guide for upstream entries.
│       ├── taxonomy.yaml     # Canonical 3-cohort declaration.
│       ├── patterns-catalog.yaml  # Upstream machine-readable index (embedded into catalog.yaml).
│       ├── llms.txt          # Upstream's AI-tool discovery.
│       └── agents.md         # Upstream's programmatic-consumption guide.
│
└── scripts/
    ├── generate_catalog.py   # Builds catalog.yaml from this repo + vendored tree.
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
        ↓ release-driven vendir sync
vendored/blueprints/  +  docs/{recipes,capabilities,frameworks,stack,cross-cutting}/
        ↓ scripts/generate_catalog.py
catalog.yaml
        ↓ HTTP fetch (one URL)
agent-scaffold (CLI)
```

catalog.yaml is the contract; nothing else in this repo is required reading for consumers.
