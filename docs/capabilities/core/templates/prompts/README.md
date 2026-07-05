# Prompts

Your agent's prompts live here as editable plain-text files. `load_prompt("system")`
returns the text of `system.txt`; add more prompts as sibling files (e.g.
`summarize.txt`, loaded with `load_prompt("summarize")`).

```python
from agent.prompts import load_prompt

system = load_prompt("system")  # -> the text of system.txt, stripped
```

Editing a prompt file takes effect on the next run — no code change. The loader
strips surrounding whitespace and caches per name for the process lifetime, so
`system.txt` is the single source of truth for how the agent behaves.

Keep `system.txt` to the prompt itself — its entire contents (minus surrounding
whitespace) are sent to the model, so notes-to-self belong here in the README,
not in the prompt file. The text can still use Markdown formatting; the `.txt`
extension just keeps prompt files out of doc tooling.
