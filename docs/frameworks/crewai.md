# Framework: CrewAI

**Language:** Python
**Install:** `uv add crewai`
**Version pinned:** >=0.28.0

## Core abstractions

- **Agent:** An LLM-powered entity with a role, goal, backstory, and tools. Agents have a persona that shapes their behavior.
- **Task:** A unit of work with a description, expected output, and optionally an assigned agent. Tasks can depend on other tasks.
- **Crew:** A team of agents working together on tasks. The crew defines the process (sequential, parallel, or hierarchical).
- **Process:** How agents execute tasks — `sequential` (one after another), `hierarchical` (manager delegates), or custom.
- **Tool:** A function the agent can call. CrewAI tools are based on LangChain's tool interface.

## Patterns it supports well

- **Multi-Agent Flat** — The canonical use case. Define a crew with specialized agents, assign tasks, run. Built-in collaboration.
- **Multi-Agent Hierarchical** — Set `process=Process.hierarchical` and designate a `manager_agent`. The manager delegates tasks to workers.
- **Prompt Chaining** — Sequential task execution where each task's output feeds the next.
- **ReAct** — Individual agents use a ReAct loop internally when they have tools.

## Patterns where it's awkward

- **Routing / Classification** — CrewAI is designed for collaboration, not intent routing. Use Pydantic AI instead.
- **RAG** — Possible via tools but there's no built-in retrieval. Better handled by a dedicated RAG framework.
- **Parallel fan-out on data** — CrewAI's parallelism is at the agent/task level, not data-level. For batch processing N items, use `asyncio.gather()` instead.
- **Fine-grained state control** — No checkpointing or state graph. The crew runs to completion.

## Idiomatic minimal example

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

## Strengths

- **Multi-agent first** — The best framework for teams of agents working together. Crew/Agent/Task is a natural mental model.
- **Role-based agents** — Backstory + role + goal gives agents strong personas without complex prompt engineering.
- **Built-in delegation** — Hierarchical process with manager delegation works out of the box.
- **Low code for simple cases** — A 2-agent crew with sequential tasks is ~20 lines.

## Trade-offs

- **Opinionated** — The Crew/Agent/Task model doesn't fit every pattern. Single-agent workflows feel over-engineered.
- **Token-heavy** — Agent backstories, task descriptions, and inter-agent messages consume many tokens. Costs add up.
- **Less control** — The internal ReAct loop and delegation logic are opaque. Hard to customize behavior mid-execution.
- **LangChain dependency** — Tools and some internals depend on LangChain, adding to the dependency tree.
- **Debugging** — Multi-agent interactions are hard to trace. Add verbose logging.

## Used in this repo

| Prototype | Role |
|-----------|------|
| `ops-crew` | Planned for flat multi-agent DevOps/Security/Database crew (skeleton) |

## Reference implementations

- [recipes/ops-crew.md](../recipes/ops-crew.md) — Multi-agent ops crew (skeleton)
