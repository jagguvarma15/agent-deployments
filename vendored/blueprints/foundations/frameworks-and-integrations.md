# Frameworks & Integrations

A map from the patterns in this repo to their typical realization in popular agent frameworks. This guide is a *map*, not a tutorial — read it to orient, then read the framework's own docs to build.

## How frameworks relate to blueprints

Blueprints describe the *shape* of a system: components, data flow, failure modes, when a pattern fits. Frameworks are concrete implementations of those shapes plus opinions about state, persistence, tool registration, and orchestration. A single pattern can typically be built in any framework — the tradeoffs are in ergonomics, debuggability, and what comes "for free."

This repo stays framework-agnostic on purpose. If a pattern's correctness depends on a specific framework, the design is leaking implementation into the architecture layer. Frameworks change quickly; patterns change slowly.

## The mapping table

Rows are patterns documented in this repo. Cells name the *one* idiomatic primitive each framework uses to express that pattern. Where a framework has no dedicated primitive, the cell reads `(general approach)` — you can still build the pattern, but you're composing from lower-level pieces.

| Pattern | LangGraph | Claude Agent SDK | CrewAI | AutoGen | LlamaIndex | MCP |
|---------|-----------|------------------|--------|---------|------------|-----|
| **Prompt Chaining** | `StateGraph` nodes in series | sequential calls | `Task` sequence in a `Crew` | sequential `AssistantAgent` calls | `QueryPipeline` | (not an MCP concern) |
| **Parallel Calls** | parallel branches in `StateGraph` | concurrent client calls | (general approach) | `GroupChat` round-robin | `QueryPipeline` parallel modules | (not an MCP concern) |
| **Orchestrator-Worker** | supervisor node + worker nodes | parent agent + sub-agents | `Crew` with `Process.hierarchical` | `GroupChatManager` | sub-question query engine | (not an MCP concern) |
| **Evaluator-Optimizer** | conditional edge loop | manual retry loop | (general approach) | critic + generator agents | response evaluators | (not an MCP concern) |
| **ReAct** | `create_react_agent` | tools loop | `Agent` with tools | `AssistantAgent` with function calls | `ReActAgent` | (tool layer, not orchestration) |
| **Plan & Execute** | planner node + executor subgraph | plan tool + execute tool loop | `Crew` with `Process.sequential` planner | `Society of Mind` pattern | plan-and-solve agent | (not an MCP concern) |
| **Tool Use** | `ToolNode` | `tools=[...]` | `Agent.tools=[]` | function-calling schemas | `FunctionTool` | **MCP servers are the tool registry** |
| **Memory** | `MemorySaver` / checkpointer | conversation history + memory tools | `Memory` module | conversation buffer | `ChatMemoryBuffer` | (resource server) |
| **RAG** | retriever node + branch | retrieval tool + system prompt | `Agent` with retrieval tool | retrieval-augmented agent | `VectorStoreIndex` + query engine | MCP server fronting a vector DB |
| **Reflection** | self-loop edge | self-critique tool | (general approach) | critic agent feedback | response synthesizer with feedback | (not an MCP concern) |
| **Routing** | conditional edge by classifier | router as tool / system prompt | `Crew` with `manager_llm` | classifier + handoff | router query engine | (not an MCP concern) |
| **Multi-Agent** | subgraphs + supervisor | sub-agents | `Crew` with multiple `Agent`s | `GroupChat` | multi-agent workflow | (not an MCP concern) |
| **Event-Driven** | (external trigger + LangGraph) | (external trigger + SDK) | (external trigger + CrewAI) | (external trigger + AutoGen) | (external trigger + LlamaIndex) | (server can be triggered, but orchestration is outside MCP) |
| **Saga** | (general approach) | (general approach) | (general approach) | (general approach) | (general approach) | (not an MCP concern) |
| **Human in the Loop** | `interrupt` / breakpoints | tool that pauses for approval | (general approach) | `UserProxyAgent` | (general approach) | (not an MCP concern) |

Cells marked `(general approach)` mean the framework can express the pattern but doesn't have a dedicated primitive — you compose it from tools, state, and control flow.

## When each framework fits

**LangGraph** — Reach for it when agent state is graph-shaped, you want persistent checkpoints, or you need first-class support for conditional edges and interrupts. The mental overhead is the explicit state schema; the payoff is observability and time-travel debugging.

**Claude Agent SDK** — Reach for it when you're building specifically on Claude and want the SDK to handle the tool loop, context management, and sub-agent coordination with minimal boilerplate. Closest to the metal of Anthropic's API. Best when provider lock-in is acceptable.

**CrewAI** — Reach for it when the natural shape is "specialists collaborating" and you want a high-level abstraction over multi-agent coordination. The opinionated `Agent` / `Task` / `Crew` / `Process` model fits role-based agents well; it's less natural for tight loops.

**AutoGen** — Reach for it for research-shaped, conversational multi-agent setups where group chat is the primary coordination mechanism. Strong for code-generation agents that critique each other. The conversational frame is its strength and its constraint.

**LlamaIndex** — Reach for it when retrieval is central — Q&A, search, knowledge-grounded chat. The query engine abstraction beats hand-rolled RAG when your data has structure. The agent layer is competent but not the headline.

**MCP (Model Context Protocol)** — Not a framework. It's a protocol for exposing tools, resources, and prompts to LLM clients via standardized servers. Use it when tools need to be reusable across multiple agents or hosts (Claude Desktop, custom clients, IDEs). See the MCP-specific section below.

## MCP-specific guidance

MCP is the dominant standard for tool-distribution and lives at the intersection of several patterns in this repo, so it deserves its own treatment.

**What it is, in one paragraph.** MCP (Model Context Protocol) is an open standard that defines how an LLM client (Claude Desktop, an IDE extension, a custom agent) discovers and invokes tools served by external processes. An MCP server exposes a set of tools, resources, and prompts; clients connect, list, and call them via a JSON-RPC protocol. The result is that the *agent* no longer hardcodes its tool list — it inherits the union of tools from whichever servers it's connected to.

**Where it intersects this repo's patterns:**

- [Tool Use](../patterns/tool_use/overview.md) — MCP is the standardized form of the tool registry. Instead of bespoke `function_schemas`, you connect to MCP servers and the agent gets tools by reference. See `patterns/tool_use/design.md` for how this maps to the registry component.
- [RAG](../patterns/rag/overview.md) — A vector DB MCP server lets multiple agents share one retrieval surface without re-implementing chunking/embedding/search per agent.
- [Memory](../patterns/memory/overview.md) — MCP resources are well-suited for cross-agent memory (one server, many readers).
- [Multi-Agent](../patterns/multi_agent/overview.md) — Sub-agents inheriting the same MCP server set share a tool vocabulary without explicit handoff logic.

**Security implications.** Because MCP servers run as separate processes outside the agent's direct control, they introduce a supply-chain surface:

- **Server allow-listing.** Don't let an agent connect to arbitrary MCP servers. Maintain an explicit allow-list per environment.
- **Tool description spoofing.** Tool descriptions are LLM-readable text; a malicious server can embed prompt-injection payloads. Validate descriptions out-of-band before enabling a server.
- **Scope restrictions.** MCP servers can expose destructive tools. Run servers with least-privilege credentials; never let the agent invoke a destructive tool without out-of-band confirmation.
- **Version pinning.** Lock server versions in production. A server update can silently change tool behavior the agent has been trained on.

These concerns deserve a fuller treatment than this map. They belong in a security foundations doc, which is a planned follow-up.

**Practical guidance:**

- Prefer MCP for tools that are **reused across multiple agents or hosts** (filesystem, vector DB, ticketing, observability backends).
- Prefer **in-process tools** for tight-loop performance, single-agent specialization, or anything stateful in a way MCP doesn't model well.
- An agent can use both: MCP for shared tools, in-process for specialized ones. The registry abstraction in [tool-use design](../patterns/tool_use/design.md) accommodates both.

## What this guide deliberately doesn't cover

- **Framework tutorials.** Read the framework's own docs.
- **Code samples.** This is a map; framework-specific code lives in the framework's docs and in `agent-deployments` recipes.
- **Performance benchmarks.** "Which framework is fastest" is the wrong question — pattern fit and team familiarity dominate framework speed for almost all production agents.
- **Version-specific gotchas.** Framework APIs change quarterly; this map names *concepts*, not exact symbols.
- **Choosing a framework.** That's a team and constraint decision (existing language stack, hosting target, observability requirements, lock-in tolerance), not a pattern decision.

## Related

- [Choosing a Pattern](./choosing-a-pattern.md) — Pick the pattern first; the framework is the second decision.
- [Tool Use → Design](../patterns/tool_use/design.md) — How MCP fits into the tool registry component.
- [Blueprints → Deployments](../composition/blueprints-to-deployments.md) — Production recipes name their framework explicitly.
