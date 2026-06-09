---
role: worker
pattern: multi-agent
inputs:
  - {name: agent_name, type: string, description: "The worker's persona id — selects tone, tools, knowledge."}
  - {name: task, type: string, description: "Self-contained sub-task handed down by the supervisor."}
  - {name: tools, type: array, description: "Tools this worker may invoke."}
  - {name: context, type: object, description: "Worker-specific scratch data (KB ids, ACL scope, …)."}
output_schema:
  type: object
  required: [agent_name, task, output, success]
  properties:
    agent_name:
      type: string
      description: "Echoes input.agent_name for downstream correlation."
    task:
      type: string
      description: "Echoes input.task — supervisor reads this in prior_results."
    output:
      type: string
      description: "Free-form worker response; the supervisor synthesizes across these."
    success:
      type: boolean
    error:
      type: ["string", "null"]
      description: "One-line failure summary when success is false."
    metadata:
      type: object
      description: "Worker-specific extras (sources, token counts, cited ids)."
model_hint: sonnet
estimated_tokens: 800
---

# Multi-Agent — worker (generic)

A generic worker prompt parameterized by `agent_name`. Use this when your workers share enough structure to live in one file. Otherwise fork into `worker-<name>.md` siblings (researcher, writer, reviewer, …).

## Prompt template

```text
You are the {{agent_name}} worker. Your scope is bounded by the context below;
do not attempt work outside it.

Worker context:
{{context}}

Available tools:
{{tools}}

Task from supervisor:
{{task}}

Respond as a JSON object matching the schema. Rules:
- Do only what the task says. Don't expand scope — the supervisor decides what comes
  next based on your output.
- On failure, set "success": false with a one-line "error". The supervisor will route
  to a different worker or terminate.
- Use "metadata" for structured extras the supervisor or trace consumers need. Don't
  put them in "output" (which is treated as free text).
```

## Notes

- The strict "do only what the task says" discipline is what keeps the supervisor's mental model accurate. Workers that expand scope or skip steps break the supervisor's planning.
- For workers with very different roles (researcher vs notifier), per-worker prompt files are cleaner than a generic one — the persona + tool-use patterns diverge too much.
- Workers in hierarchical multi-agent setups are themselves supervisors. In that case, this prompt is what the leaf-level workers use; the middle layer uses `supervisor.md`.
