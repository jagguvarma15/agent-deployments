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
| `restaurant-rebooking` | Event-Driven + Multi-Agent (flat) | `patterns/event-driven/` · `patterns/multi-agent/` (flat variant) |

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

## Contributing

When adding a new blueprint, you must:

1. Identify the corresponding pattern(s) in `agent-blueprints`
2. Add the Composes section to the recipe linking back to the pattern
3. Update this file with the new mapping
4. Coordinate a PR to `agent-blueprints` adding a cross-link back to this recipe
