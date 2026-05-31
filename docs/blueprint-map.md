# Blueprint Map

Full mapping between `agent-deployments` recipes and `agent-blueprints` patterns.

> [`agent-blueprints`](https://github.com/jagguvarma15/agent-blueprints) teaches
> architecture at three tiers: Overview, Design, Implementation.
> Each blueprint below links to the relevant pattern pages.

## Recipe-to-pattern mapping

| Recipe | Primary pattern(s) | Blueprint links |
|--------|-------------------|-----------------|
| `customer-support-triage` | Routing + Tool Use | `patterns/routing/` (overview, design, implementation) · `patterns/tool-use/` · `foundations/choosing-a-pattern.md` |
| `docs-rag-qa` | RAG | `patterns/rag/` (overview, design, implementation) |
| `research-assistant` | ReAct + Tool Use | `patterns/react/` (overview, design, implementation) · `patterns/tool-use/` · `patterns/react/evolution.md` |
| `content-pipeline` | Prompt Chaining + Evaluator-Optimizer | `workflows/prompt-chaining/` · `workflows/evaluator-optimizer/` · `composition/` |
| `code-review-agent` | Plan & Execute + Reflection | `patterns/plan-and-execute/` · `patterns/reflection/` · `patterns/plan-and-execute/evolution.md` |
| `ops-crew` | Multi-Agent (flat) | `patterns/multi-agent/` (flat variant) |
| `parallel-enricher` | Parallel Calls | `workflows/parallel-calls/` |
| `memory-assistant` | Memory | `patterns/memory/` |
| `hierarchical-agent` | Multi-Agent (hierarchical) | `patterns/multi-agent/` (hierarchical variant) |
| `restaurant-rebooking` | Event-Driven + Multi-Agent (flat) | `patterns/event-driven/` · `patterns/multi-agent/` (flat variant) — first recipe to declare `capabilities:` end-to-end |

## How to read this

Each blueprint's README opens with a **Blueprint Map** block that links directly
to the relevant `agent-blueprints` pages. For example:

```markdown
## Blueprint Map

- Overview: agent-blueprints/patterns/react/overview.md
- Design: agent-blueprints/patterns/react/design.md
- Implementation: agent-blueprints/patterns/react/implementation.md
- Evolution: agent-blueprints/patterns/react/evolution.md
```

## Visual mapping

```
agent-blueprints                          agent-deployments
─────────────────                         ──────────────────

foundations/choosing-a-pattern.md    ──►   customer-support-triage
                                           (why Routing, not ReAct)

patterns/routing/                    ──►   customer-support-triage
patterns/tool-use/                   ──►   customer-support-triage, research-assistant

patterns/rag/                        ──►   docs-rag-qa

patterns/react/                      ──►   research-assistant

patterns/plan-and-execute/           ──►   code-review-agent
patterns/reflection/                 ──►   code-review-agent

patterns/multi-agent/  (flat)        ──►   ops-crew, restaurant-rebooking
patterns/multi-agent/  (hierarchical)──►   hierarchical-agent

patterns/event-driven/               ──►   restaurant-rebooking

patterns/memory/                     ──►   memory-assistant

workflows/prompt-chaining/           ──►   content-pipeline
workflows/evaluator-optimizer/       ──►   content-pipeline
workflows/parallel-calls/            ──►   parallel-enricher

composition/                         ──►   content-pipeline (headline example)
                                           hierarchical-agent
```

## Capabilities layer

Layered orthogonally on top of the recipe → pattern mapping, [`docs/capabilities/`](capabilities/) describes the **provisioning contracts** consumed by `agent-scaffold up` (≥ v0.3):

```
docs/capabilities/
  vector_db/{qdrant, chroma, pgvector}
  cache/{redis}
  relational/{postgres}
  queue/{kafka, redis-streams}
  obs/{langsmith, langfuse, grafana-stack}
  eval/{promptfoo}
  frontend/{nextjs-chat, streamlit}
  host/{vercel, railway, fly}
```

A recipe opts in by declaring `capabilities: [...]` in its frontmatter. The scaffold's resolver matches each id against the catalog and threads the resolved bodies through context assembly + orchestrator bootstrap steps. See [`docs/capabilities/README.md`](capabilities/README.md) for the schema and authoring guide.

## Contributing

When adding a new blueprint, you must:

1. Identify the corresponding pattern(s) in `agent-blueprints`
2. Add the Composes section to the recipe linking back to the pattern
3. Update this file with the new mapping
4. Coordinate a PR to `agent-blueprints` adding a cross-link back to this recipe
5. If the recipe needs new infra not in [`docs/capabilities/`](capabilities/), add the capability file alongside the recipe PR (or in a sibling PR)
