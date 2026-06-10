# Skill loader / Stage 2 judge prompt

Reference prompt template the agent runtime uses to pick which skills to activate when keyword matching returns multiple candidates. Small / fast model (Haiku-class) is sufficient.

## Template

```text
You are a skill router. Given a user message and a list of candidate skills,
pick AT MOST {{ max_pick }} skills the agent should load for this turn.

A skill should be picked when:
  - Its description and when_to_use plausibly match the user's intent.
  - The procedure it encodes is needed for THIS turn (not just generally useful).

Do NOT pick skills that:
  - Only marginally apply.
  - Duplicate each other's procedure.
  - Would conflict in their actions for this turn.

Reply with a single JSON array of skill ids. Empty array if none apply.
Do not include any other text.

User message:
"""
{{ user_message }}
"""

Candidates:
{% for skill in candidates %}
- id: {{ skill.id }}
  name: {{ skill.name }}
  description: {{ skill.description }}
  when_to_use: {{ skill.when_to_use }}
{% endfor %}
```

## Variables

| Variable | Type | Source |
|---|---|---|
| `max_pick` | int | Runtime config; typically `2`. |
| `user_message` | string | The current user turn's message body. |
| `candidates` | list of registry entries | Output of Stage 1 keyword match, top-K = 5. |

## Expected output

A JSON array of strings, each a skill id from the candidate set. Empty array is valid (no skill matches).

```json
["web-search-loop"]
```

```json
["web-search-loop", "citation-formatting"]
```

```json
[]
```

## Notes

- Hard cap on output length (~100 tokens) at the API call so the model can't ramble.
- Strict JSON schema enforcement at the SDK level catches malformed output.
- If the model returns ids not in the candidate set, the runtime drops them with a warning.
- The prompt deliberately doesn't include skill bodies — only descriptions. Loading bodies before picking would defeat the lazy-load economics.
