---
id: core.prompts
kind: core
implements:
  port: core
  interface_version: "1.0"
layer: agent
provides: [prompts, prompt_loader]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: Owned prompts
  description: "Editable Markdown prompt files + a loader — the agent's system prompt lives in prompts/system.txt, not a hardcoded string. Part of the T0 chat substrate."
  capabilities_provided: [prompts, prompt_loader]
  required_credentials: []
emit_files:
  - source: templates/prompts/**
    dest: agent/prompts/
deploy_configs: []
docs: |
  Emits the agent/prompts/ package: editable Markdown prompt files plus a
  load_prompt(name) loader. The generated agent reads its system prompt from
  agent/prompts/system.txt via load_prompt("system") instead of hardcoding a
  string, so the developer owns and edits the prompt without touching code. The
  scaffold emits the loader and a starter system.txt; the recipe/model fills in
  the actual prompt content and adds any extra named prompts as sibling .txt
  files. Do NOT redefine the loader or inline the system prompt — import it:
  `from agent.prompts import load_prompt`.
tags: [core, prompts, ownership]
when_to_load: "recipe tier is T0 or higher (the tier preset seeds core.prompts)"
---

# Core: Owned prompts

The prompt-ownership substrate emitted at the **T0** tier. It makes the agent's
system prompt an editable file rather than a string buried in code, so the
developer owns behavior without a code change.

## Emitted files

`emit_files` copies `templates/prompts/**` into the project's `agent/prompts/`
package:

| File | Role |
|---|---|
| `loader.py` | `load_prompt(name)` — reads `agent/prompts/<name>.txt`, stripped and cached. Rejects path-like names. |
| `system.txt` | The starter system prompt. Edit it to change the agent's behavior. |
| `__init__.py` | Re-exports `load_prompt` (`from agent.prompts import load_prompt`). |
| `README.md` | How to edit prompts and add new named ones. |

The copier never overwrites a file the model emitted at the same path, so a
recipe can ship its own `system.txt` while inheriting the loader.

## Wiring

The agent loads its system prompt once at startup — `system = load_prompt("system")`
— and passes it to the model. Extra prompts (few-shot exemplars, a summarizer
instruction) are sibling `.txt` files loaded by stem: `load_prompt("summarize")`.
Editing a `.md` file takes effect on the next run.

## See also

- The generated `.agent/spec.md` records the tier that seeded this capability.
