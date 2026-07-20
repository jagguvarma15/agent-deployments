---
id: core.spec
kind: core
implements:
  port: core
  interface_version: "1.0"
layer: agent
provides: [spec, agent_spec]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: Agent spec
  description: "The durable machine-readable statement of what the agent is: recipe, tier, role, resolved capability stack, model, and environment contract, written to .agent/spec.md. The T0 anchor every later tier builds on."
  capabilities_provided: [spec, agent_spec]
  required_credentials: []
emit_files: []
deploy_configs: []
docs: |
  The scaffold writes .agent/spec.md itself after generation — it is a
  deterministic render of the resolved inputs (recipe, tier, role, capability
  stack, model, environment contract), not an LLM output. Do NOT author
  .agent/spec.md in the generated files; the scaffold owns that path. Treat
  the spec as the project's source of truth: the agent's role and system
  prompt must match its Role section, code must reference the model id its
  Target section declares, and the environment contract it lists is the
  complete set of variables the project may read. Keep .agent/spec.md
  committed to version control (unlike .agent/runs/ and .agent/trace.jsonl,
  which are runtime output) — future regenerations reconcile against it.
tags: [core, spec, contract, provenance]
when_to_load: "always at T0 and above (the tier preset seeds core.spec)"
---

# Core: Agent spec

The anchor emitted at the **T0** tier — and therefore present at every tier.
`.agent/spec.md` is the durable, machine-readable statement of what the agent
*is*: the recipe it realizes, the tier it was built at, its role, the resolved
capability stack, the target model, and the environment contract. Where the
run summary records what *happened* in a generation run, the spec records what
the project *is*.

## Who writes it

The scaffold, not the model. After every generation the scaffold renders the
spec deterministically from the resolved inputs — no LLM call, no timestamp —
so regenerating an unchanged project produces a clean diff rather than churn.
Generated code must never author or overwrite `.agent/spec.md`; the path is
scaffold-owned.

## Contract

The rendered document carries these sections, in order:

| Section | Content |
|---|---|
| `## Recipe` | Recipe slug and title, status, pattern, topology, the build tier, and the deployments snapshot sha. |
| `## Target` | Language / framework and the runtime model id. |
| `## Role` | The agent's role text — the persona the backend system prompt realizes. |
| `## Capabilities` | The resolved capability stack (the tier expansion plus explicit picks). |
| Environment contract | Every variable the project reads, from the stack's declared env vars. |

Consumers may parse the section headings; their names and order are stable.

## Version-control rule

`.agent/spec.md` is meant to be committed — it is the living spec future
edits and regenerations reconcile against. The rest of `.agent/` produced at
runtime (`runs/`, `trace.jsonl`) is output and stays gitignored. The scaffold
applies both defaults.

## Why it is a capability

Making the spec a `core` capability puts it in the tier ladder (T0 seeds it),
in the catalog card a consumer can inspect, and in the generation context —
so the model is told, in one place, what the artifact is and that it must not
compete with it. The capability itself emits no files and requires nothing:
its whole contract is the rule set above.
