# Terminology

Precise definitions for terms used throughout this repository. These terms are overloaded across the industry — here, they have specific meanings.

## Core Concepts

### LLM (Large Language Model)
A neural network trained on text that accepts a prompt and produces a completion. In this repository, "the LLM" refers to whichever model you're using — the patterns are provider-agnostic.

### Prompt
The input to an LLM. Includes a system prompt (instructions defining behavior), user messages, and optionally assistant messages (for multi-turn context). A well-structured prompt is the foundation of every pattern in this repository.

### Completion
The LLM's output in response to a prompt. May be text, structured data (JSON), or a tool call request.

### Token
The unit of text processing for LLMs. Roughly 3/4 of a word in English. Matters because LLMs have context windows measured in tokens, and cost scales with token usage.

### Context Window
The maximum number of tokens an LLM can process in a single call (prompt + completion combined). Ranges from ~4K to ~200K+ tokens depending on the model. A hard constraint that shapes how you design message histories, retrieval systems, and memory patterns.

## System Components

### Tool
A function the LLM can request to call. The LLM doesn't execute the tool — it produces a structured request (tool name + arguments), your code executes it, and you feed the result back to the LLM. Tools bridge "thinking" (the LLM) and "doing" (your code).

Examples: search an API, query a database, read a file, perform a calculation.

### Tool Schema
A structured definition describing a tool's name, purpose, and expected arguments. Provided to the LLM so it knows what tools are available and how to call them. Typically JSON Schema format.

### Tool Registry
A mapping from tool names to their implementations. When the LLM requests a tool call, the registry resolves the name to actual code.

### State
Information that persists across steps within a single run. Examples: the message history in a conversation, a plan being executed step-by-step, or accumulated search results. State is what makes multi-step systems "remember" what happened earlier in the current task.

### Memory
Information that persists *across* runs. Short-term memory is state within a session. Long-term memory is information stored in an external system (database, vector store, file) and retrieved in future sessions. See the [Memory pattern](../patterns/memory/overview.md).

## Patterns and Architectures

### Workflow
An orchestrated sequence of LLM calls where **the code controls the flow**. The developer decides which LLM calls happen, in what order, and under what conditions. The LLM generates content within each step but does not choose the next step.

Workflows are predictable, testable, and easy to debug. They are the right choice when you know the process in advance.

See: [Workflows](../workflows/README.md)

### Agent
An LLM-driven system where **the model controls the flow**. The LLM decides which tool to call, when to continue or stop, and how to respond to new information. The developer provides tools, constraints (max iterations, guardrails), and a goal — the LLM figures out the path.

Agents are flexible and adaptive but harder to predict and debug. They are the right choice when the process cannot be determined in advance.

See: [Agent Patterns](../patterns/README.md)

### Pattern
A reusable architectural design for an LLM system. Patterns describe the *shape* of a system — the components, their relationships, and the control flow between them — without specifying implementation details.

### Composition
Combining multiple patterns into a single system. Most production systems compose several patterns. See [Composition](../composition/README.md).

## Control Flow Concepts

### Loop
A cycle where the LLM is called repeatedly until a termination condition is met. In workflows, the loop condition is coded (e.g., "repeat 3 times" or "until quality score > 0.8"). In agents, the LLM itself decides when to exit the loop.

### Routing
Directing input to different processing paths based on classification. Can be LLM-driven (the model classifies the input) or rule-based (your code checks conditions). See the [Routing pattern](../patterns/routing/overview.md).

### Orchestration
Coordinating multiple LLM calls or agents to accomplish a complex task. An orchestrator breaks down work, delegates to workers, and synthesizes results.

### Delegation
Passing a subtask from one component (supervisor, orchestrator) to another (worker agent, specialized LLM call). The delegator defines the task; the delegate executes it.

### Observation
The result of a tool call or external action, fed back to the LLM as context for the next step. Observations close the reasoning-action loop in agent patterns.

## Quality and Safety

### Guardrail
A constraint that prevents an LLM system from producing harmful, off-topic, or low-quality output. Can be input validation, output filtering, iteration limits, or scope restrictions.

### Grounding
Anchoring LLM output in factual source material. RAG is the primary grounding technique — the LLM generates responses based on retrieved documents rather than purely from its training data.

### Hallucination
When an LLM generates plausible but factually incorrect content. Patterns like RAG and reflection help mitigate hallucination.

### Evaluation
Assessing the quality of LLM output against criteria. Can be automated (LLM-as-judge, rule-based checks) or human (manual review). The [evaluator-optimizer workflow](../workflows/evaluator-optimizer/overview.md) and [reflection pattern](../patterns/reflection/overview.md) build evaluation into the system loop.
