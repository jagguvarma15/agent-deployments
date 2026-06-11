---
id: crewai
language: python
package: crewai
versions:
  minimum: ">=0.70.0"
  last_known_good: "0.70.0"
  notes: ">=0.70.0 is the floor at which the kwargs-only `Crew()` constructor + the split-out memory module are stable; older drops break in unobvious ways."
---

# Framework: CrewAI

**Language:** Python
**Install:** `uv add crewai`
**Version pinned:** >=0.70.0

## When to choose CrewAI

CrewAI is the right fit when the agent shape is a team — multiple role-specialized agents collaborating on tasks, with a sequential or hierarchical process driving their interaction. Multi-agent is the framework's central concept; Crew / Agent / Task is a natural mental model and the abstractions earn their keep at exactly two or more agents. Role-based agents get strong personas from a `role` + `goal` + `backstory` triple without explicit prompt engineering. Built-in delegation works out of the box: set `process=Process.hierarchical` and designate a `manager_agent` to get supervisor-shaped workflows. Low code for simple cases — a 2-agent crew with sequential tasks is roughly twenty lines.

Core abstractions:

- **Agent:** An LLM-powered entity with a role, goal, backstory, and tools. Agents have a persona that shapes their behavior.
- **Task:** A unit of work with a description, expected output, and optionally an assigned agent. Tasks can depend on other tasks.
- **Crew:** A team of agents working together on tasks. The crew defines the process (sequential, parallel, or hierarchical).
- **Process:** How agents execute tasks — `sequential` (one after another), `hierarchical` (manager delegates), or custom.
- **Tool:** A function the agent can call. CrewAI tools are based on LangChain's tool interface.

## Minimal agent

```python
from crewai import Agent, Task, Crew, Process

researcher = Agent(
    role="Researcher",
    goal="Find accurate information about the topic",
    backstory="You are an expert researcher with attention to detail.",
    tools=[search_tool],
)

writer = Agent(
    role="Writer",
    goal="Write clear, concise summaries",
    backstory="You are a technical writer who excels at making complex topics accessible.",
)

research_task = Task(
    description="Research {topic}",
    expected_output="Detailed research notes with sources",
    agent=researcher,
)

write_task = Task(
    description="Write a summary based on the research",
    expected_output="A clear, concise summary",
    agent=writer,
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,
)

result = crew.kickoff(inputs={"topic": "AI agents"})
```

## Tools

Tools are LangChain tools — instantiate or decorate a callable with `@tool` and pass the list on the `Agent`. CrewAI bridges them onto its own dispatch path so a tool reaches the model with the same OpenAI-format schema it would under LangChain. Tools are agent-scoped: assigning a tool to a researcher and not to a writer is the easy way to enforce role boundaries.

## Structured output

CrewAI tasks declare an `expected_output` string and (in recent minors) accept a Pydantic `output_pydantic=` argument that constrains the task's final result to a typed schema. Validation runs once at task completion; on failure the task retries with the validation error included in the next turn. The crew's final output is whatever the last task in the sequence emitted, typed or string.

## Memory

CrewAI ships a dedicated `crewai.memory` module providing short-term (in-flight crew run), long-term (cross-run), and entity memory backends. Configure on the `Crew` via the `memory=True` flag or by passing a custom memory store. For deeper persistence (across sessions, multi-tenant), wire the memory module against an external store; the module's interface is pluggable.

## Streaming

CrewAI does not natively expose token-by-token streaming to the caller. `crew.kickoff()` is a blocking call that returns the final crew output; intermediate task outputs surface via the per-task callback hook, not a stream. For UIs that need live progress, drive the callback to push events onto an out-of-process channel (Redis, an in-process queue) and stream from that channel.

## Observability

CrewAI exposes per-task callbacks (`task.callback=fn`) where `fn` receives the typed task result and can fan out to logging, tracing, or metrics. The framework itself does not ship a dedicated tracing backend; common practice is to wrap LLM calls and tool invocations through LangChain's tracing layer (the LangSmith integration applies transitively because CrewAI builds on LangChain tools). For OTel, wrap the crew kickoff with `tracer.start_as_current_span` and let nested LangChain spans propagate.

## Anti-patterns

- **Routing / Classification** — CrewAI is designed for collaboration, not intent routing. Use Pydantic AI instead.
- **RAG** — Possible via tools but there's no built-in retrieval. Better handled by a dedicated RAG framework.
- **Parallel fan-out on data** — CrewAI's parallelism is at the agent/task level, not data-level. For batch processing N items, use `asyncio.gather()` instead.
- **Fine-grained state control** — No checkpointing or state graph. The crew runs to completion.
- **Token-heavy by design.** Agent backstories, task descriptions, and inter-agent messages consume many tokens. Costs add up; budget per crew run.
- **Less mid-flight control.** The internal ReAct loop and delegation logic are opaque. Hard to customize behavior mid-execution; reach for LangGraph when you need explicit edges.
- **LangChain dependency footprint.** Tools and some internals depend on LangChain, adding to the dependency tree. Worth modeling in `pyproject.toml` if you're already shipping LangGraph or LangChain — the deps deduplicate.
- **Debugging multi-agent runs is hard.** Inter-agent message flow is not first-class observable. Add verbose logging early.

## Composition matrix

- **Multi-Agent Flat** — The canonical use case. Define a crew with specialized agents, assign tasks, run. Built-in collaboration.
- **Multi-Agent Hierarchical** — Set `process=Process.hierarchical` and designate a `manager_agent`. The manager delegates tasks to workers.
- **Prompt Chaining** — Sequential task execution where each task's output feeds the next.
- **ReAct** — Individual agents use a ReAct loop internally when they have tools.

## MCP integration

CrewAI accepts MCP tools through `crewai_tools.mcp.MCPToolset`, which wraps a connected MCP client and exposes each discovered tool as a CrewAI `BaseTool`.

**Streamable HTTP transport (the `mcp.tavily` capability):**

```python
import os
from crewai import Agent, Task, Crew
from crewai_tools.mcp import MCPToolset

tavily_toolset = MCPToolset.from_streamable_http(
    url="https://mcp.tavily.com/mcp/",
    headers={"Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"},
)

researcher = Agent(
    role="Web Researcher",
    goal="Search and synthesize information on technical topics.",
    backstory="A senior researcher familiar with distributed-systems trade-offs.",
    tools=tavily_toolset.tools,
    llm="anthropic/claude-sonnet-4-6",
)

task = Task(
    description="Compare GraphQL vs gRPC for streaming workloads.",
    agent=researcher,
    expected_output="A structured comparison with citations.",
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
print(result)
```

**Stdio transport (subprocess-spawned servers):**

```python
postgres_toolset = MCPToolset.from_stdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-postgres", os.environ["DATABASE_URL"]],
)
```

For multi-agent crews where different roles need different MCP servers, instantiate one `MCPToolset` per server and attach selectively to each agent's `tools=` parameter.

## Version notes

`>=0.70.0` is the floor at which the kwargs-only `Crew()` constructor + the split-out memory module are stable; older drops break in unobvious ways.

| Version | Status | Notes |
|---------|--------|-------|
| `< 0.70.0` | Unsupported | Pre-kwargs-only `Crew()` constructor; positional args silently bind to the wrong fields. Memory was inlined rather than a separate module — recipes that import `crewai.memory.*` will fail. |
| `>=0.70.0` | Recommended | Current pin in the frontmatter. Validated against [`../recipes/ops-crew.md`](../recipes/ops-crew.md). |
| `0.80+` | Untested | May work; CI does not validate. Re-verify `Process.hierarchical` and the memory module's import paths before bumping. |

### Upgrade gotchas

- **`Process` enum names.** `Process.sequential` vs `Process.hierarchical` is the documented split. Older drafts used `"sequential"` / `"hierarchical"` strings; these are coerced loosely but the enum path is the durable one.
- **Memory module split.** The memory feature moved to `crewai.memory` as its own module mid-0.6x. Recipes that import from the old inlined location need to be migrated when the doc is touched.
- **Task callback signature.** Per-task callbacks receive a typed result object (not the raw string) in the post-0.70 line. Adapting a callback that does `str.startswith(...)` on the result is a common silent-break source.

### Why these bounds

The `>=0.70.0` floor is the version at which the kwargs-only `Crew()` constructor, the split-out memory module, and the typed task-result callback surface stabilized. Pre-0.70 the API was still moving fast enough that the [`ops-crew`](../recipes/ops-crew.md) recipe pinned a different minor every release. No recorded upper bound — CrewAI's release cadence is moderate and post-0.70 has stayed additive — but treat any minor bump as a re-verify event against the ops-crew skeleton's role definitions.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `ops-crew` | Planned for flat multi-agent DevOps/Security/Database crew (skeleton) |

Reference implementations:

- [recipes/ops-crew.md](../recipes/ops-crew.md) — Multi-agent ops crew (skeleton)
