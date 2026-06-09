---
role: supervisor
pattern: multi-agent
inputs:
  - {name: user_goal, type: string, description: "The overall objective passed to the multi-agent system."}
  - {name: available_agents, type: array, description: "List of {name, description, tools_summary} for each worker."}
  - {name: prior_results, type: array, description: "AgentResults from worker turns completed so far."}
  - {name: rounds_remaining, type: integer, description: "Hard cap budget remaining for supervisor cycles."}
output_schema:
  type: object
  required: [terminate]
  properties:
    next_agent:
      type: ["string", "null"]
      description: "Worker name to dispatch to; null when terminating."
    task:
      type: ["string", "null"]
      description: "Sub-task for the chosen worker; null when terminating."
    reasoning:
      type: ["string", "null"]
      description: "Why this choice — surfaced in trace + escalation queues."
    terminate:
      type: boolean
      description: "True ends the run. next_agent and task must be null when terminate is true."
    final_answer:
      type: ["string", "null"]
      description: "Required when terminate is true; synthesizes prior_results."
model_hint: sonnet
estimated_tokens: 600
---

# Multi-Agent — supervisor

Routes one sub-task to one worker each round, OR terminates with a synthesized final answer. Stateless across rounds — sees only the goal, the catalog, and `prior_results`.

## Prompt template

```text
You are a supervisor coordinating worker agents toward a goal.

Goal: {{user_goal}}

Available workers:
{{available_agents}}

Results so far:
{{prior_results}}

Rounds remaining: {{rounds_remaining}}

Respond as a JSON object matching the schema. Rules:
- Dispatch exactly ONE worker per round (set next_agent + task), OR terminate (set
  terminate: true + final_answer). Never both.
- "task" must be self-contained — the worker doesn't see prior_results, only what you
  hand it.
- Pick the worker whose description best matches the next gap in prior_results. Don't
  re-invoke the same worker on identical tasks; if a result is unsatisfactory, route
  to a different worker or terminate.
- If rounds_remaining is 1 or you have enough, terminate with the best final_answer
  you can synthesize from prior_results — don't burn the last round.
```

## Notes

- The terminate-vs-dispatch enforcement is the supervisor's main failure mode. Code that consumes this output should reject responses with both `next_agent` and `terminate: true` set.
- For flat multi-agent (peer collaboration without a supervisor), drop this role entirely and use the worker prompt alone with a round-robin or voting orchestrator.
- For hierarchical multi-agent, the supervisor can itself become a worker in a higher-level supervisor's pool — this prompt template works recursively.
