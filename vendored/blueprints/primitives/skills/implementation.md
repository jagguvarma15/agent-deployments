# Skills — Implementation

> **Tier 3 — Implementation.** `SKILL.md` schema, loader pseudocode, trigger matching, security boundaries, pitfalls. For the conceptual shape, see [`design.md`](./design.md).

## SKILL.md schema

Every skill is a folder whose `SKILL.md` opens with YAML frontmatter. The contract:

```yaml
---
id: web-search-loop                # kebab-case, unique within the registry
name: Web Search Loop              # human-readable label
version: 0.3.0                     # semver — bump when behavior changes
description: >
  Run a multi-step web search loop: search → extract → cite. Use when the
  user asks an open-ended factual question that needs live sources.
when_to_use: >
  The user is asking a research question whose answer requires consulting
  live web content, not just the agent's training knowledge.
triggers:
  - research
  - "look up"
  - investigate
  - "find out"
  - "what does the web say about"
requires:                          # optional: declare hard dependencies
  mcp_servers: [mcp.tavily]
  tools: []                        # in-process tool names, if any
  scripts: [scripts/search.py, scripts/extract.py]
grants:                            # optional: which roles can use this skill
  roles: [researcher, analyst]
metadata:
  author: jagadesh@example.com
  tags: [research, web, citation]
---

# Web Search Loop

[Body content: markdown instructions the agent reads when this skill is selected]
```

**Required fields:** `id`, `name`, `version`, `description`, `triggers`.

**Optional fields:** `when_to_use`, `requires`, `grants`, `metadata`. Forward-compatible additive fields are tolerated by readers (the loader warns on unknown fields but doesn't fail).

The body is markdown. By convention it starts with a `# <Name>` H1, then sections like `## Steps`, `## Inputs`, `## Outputs`, `## Examples`. Aim for under 2,000 tokens of body — push detail into helper scripts.

See [`schemas/skill.schema.json`](./schemas/) for the JSON Schema definition.

## Loader (pseudocode)

```python
from pathlib import Path
from typing import Iterator

class SkillRegistry:
    """In-memory registry. Built once at boot, queried per turn."""

    def __init__(self):
        self.skills: dict[str, RegistryEntry] = {}

    def load(self, skills_root: Path) -> None:
        for skill_md in skills_root.glob("*/SKILL.md"):
            try:
                entry = _parse_skill(skill_md)
            except SchemaError as exc:
                warn(f"{skill_md}: {exc}; skipping")
                continue
            if entry.id in self.skills:
                raise StartupError(f"duplicate skill id: {entry.id}")
            self.skills[entry.id] = entry

def _parse_skill(path: Path) -> RegistryEntry:
    text = path.read_text()
    frontmatter, body = split_frontmatter(text)
    # IMPORTANT: do NOT keep the body in memory — only the body_path.
    return RegistryEntry(
        id=require(frontmatter, "id"),
        name=require(frontmatter, "name"),
        version=require(frontmatter, "version"),
        description=require(frontmatter, "description"),
        when_to_use=frontmatter.get("when_to_use", ""),
        triggers=[t.lower() for t in require(frontmatter, "triggers")],
        body_path=path,                    # loaded on demand
        scripts_dir=path.parent / "scripts",
        requires=frontmatter.get("requires", {}),
        grants=frontmatter.get("grants", {}),
    )
```

Key invariants:

- Bodies are NEVER kept in `RegistryEntry`. The whole point of the registry is to be cheap.
- Frontmatter validation is loud — schema errors warn or fail at boot, not at first invocation.
- Trigger lowercasing happens at load time, not at match time.

## Trigger matcher (pseudocode)

Two-stage matcher. Stage 1 is deterministic; Stage 2 is judgmental.

```python
def select_skills(
    user_msg: str,
    state: AgentState,
    registry: SkillRegistry,
    grants: GrantPolicy,
    judge_llm: LLM | None,
    role: str,
) -> list[RegistryEntry]:
    # Apply grants first — never even consider skills the role can't use.
    candidates = [
        s for s in registry.skills.values()
        if grants.allows(role=role, skill_id=s.id)
    ]

    # Stage 1: keyword scan.
    matched = []
    lowered = user_msg.lower()
    for skill in candidates:
        if any(t in lowered for t in skill.triggers):
            matched.append(skill)
    matched = _rank_by_trigger_match_density(matched, lowered)[:5]

    if len(matched) <= 1:
        return matched  # 0 or 1 hits — no need to consult judge_llm

    # Stage 2: LLM scoring.
    if judge_llm is None:
        return matched[:1]  # fallback: take the top-1
    return _llm_pick(matched, user_msg, state, judge_llm, max_pick=2)

def _llm_pick(skills, user_msg, state, llm, max_pick=2):
    prompt = f"""
You're picking AT MOST {max_pick} skills the agent should load to answer the user.

User said: {user_msg}

Candidates:
{format_candidates(skills)}  # name, description, when_to_use for each

Reply with a JSON array of skill ids (subset of the candidates). Empty array OK.
"""
    picked_ids = llm.json_array(prompt, schema={"type": "array", "items": {"type": "string"}})
    return [s for s in skills if s.id in picked_ids]
```

Notes:

- Trigger matching is case-insensitive and substring-based for now. If your trigger set grows large (>1k entries), consider an inverted index or trie.
- `_rank_by_trigger_match_density`: skills with multiple trigger hits score higher. Discourages over-broad single-trigger matches.
- Stage 2 LLM is a SMALL model (Haiku-class). The judgment cost should be ~1k tokens prompt + ~50 tokens response. Sub-penny per turn.

## Body injection into the agent context

Once skills are picked, the body loader reads each `SKILL.md` body and injects it into the agent's prompt context with a marker so traces can recover what was active:

```python
def inject_skill_bodies(prompt_parts: list[str], picked: list[RegistryEntry]) -> list[str]:
    for skill in picked:
        body = _read_body(skill.body_path)
        prompt_parts.append(f"<!-- ===== skill: {skill.id} v{skill.version} ===== -->")
        prompt_parts.append(body)
    return prompt_parts

def _read_body(path: Path) -> str:
    text = path.read_text()
    _frontmatter, body = split_frontmatter(text)
    return body.strip()
```

The injection happens AFTER the recipe's static system prompt and BEFORE the conversation history. That ordering matters: skills extend the system policy; they don't override the conversation.

## Helper-script execution

Skill bodies frequently say things like:

> "Run `python skills/web-search-loop/scripts/search.py <query>` and use the result."

The agent runtime needs to honor that — either via in-process subprocess invocation or via a sandbox. The pattern:

```python
def run_skill_script(skill: RegistryEntry, script_name: str, args: list[str]) -> str:
    script_path = skill.scripts_dir / script_name
    if not script_path.is_file():
        raise SkillError(f"skill {skill.id} references missing script: {script_name}")

    # Production: run in a sandbox (see foundations/sandboxed-execution.md).
    # Dev: subprocess in-process.
    if SANDBOX_MODE:
        return sandbox.run(script_path, args, timeout=30, workdir=skill.scripts_dir)
    return subprocess.run(
        ["python", str(script_path), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=skill.scripts_dir,
    ).stdout
```

Helper scripts are part of the skill's contract. Pin them to a stable interface (CLI args, stdin/stdout) so the SKILL.md instructions don't drift.

## Grant policy (pseudocode)

```python
class GrantPolicy:
    """Per-role / per-tenant skill access control."""

    def __init__(self, config: dict):
        # config maps role -> {allowed: [skill_id], denied: [skill_id]}
        self.role_grants = config

    def allows(self, *, role: str, skill_id: str) -> bool:
        grant = self.role_grants.get(role, {"allowed": []})
        if skill_id in grant.get("denied", []):
            return False
        return skill_id in grant.get("allowed", []) or grant.get("allow_all", False)
```

Production grant policies typically also include:

- **Tenant scoping** — `role + tenant_id` keys instead of just `role`.
- **Audit logging** — every `allows()` call records `(role, skill_id, decision)` to the trace.
- **Time-bounded grants** — for break-glass scenarios.

See [`schemas/grant.schema.json`](./schemas/) for the configuration schema.

## Testing strategy

Skills are testable as units, in a way most agent components aren't:

```python
def test_skill_frontmatter_valid():
    """Every committed SKILL.md parses cleanly."""
    for skill_md in PROJECT_ROOT.glob("skills/*/SKILL.md"):
        _parse_skill(skill_md)  # raises on schema error

def test_skill_triggers_fire():
    """Each skill has at least one canonical test prompt that matches its triggers."""
    for skill_md in PROJECT_ROOT.glob("skills/*/SKILL.md"):
        meta = read_frontmatter(skill_md)
        test_prompt = meta.get("metadata", {}).get("test_prompt")
        if test_prompt is None:
            continue  # opt-in
        assert any(t in test_prompt.lower() for t in meta["triggers"]), \
            f"{meta['id']}: test_prompt does not contain any declared trigger"

def test_skill_script_imports():
    """Helper scripts are importable / have no syntax errors."""
    for script in PROJECT_ROOT.glob("skills/*/scripts/*.py"):
        py_compile.compile(script, doraise=True)
```

Pair with [`composition/agentic-eval-pipeline.md`](../../composition/agentic-eval-pipeline.md) for the trajectory-level question — "did the right skill activate for this query?".

## Pitfalls

- **Triggers are too broad.** `triggers: [code]` will fire on every coding-related query. Use phrases (`"review my code"`) or compounds (`code-review`).
- **Bodies are too long.** A 10K-token SKILL.md body crowds out everything else in the agent's context. Push detail into scripts; keep the markdown focused.
- **Skills coupling to other skills.** "Skill A assumes skill B already ran" creates implicit ordering. The matcher doesn't enforce ordering. Either combine them into one skill or coordinate via state.
- **No version bumps.** Skills without versioning are invisible to dependency-update workflows. Always set `version:`.
- **Scripts that write to host fs.** A skill script that writes outside its `scripts_dir` is a sandbox-policy violation waiting to happen. Constrain writes to the workspace mount; see [`foundations/sandboxed-execution.md`](../../foundations/sandboxed-execution.md).
- **Grants forgotten.** Skipping the grant model in single-user dev is fine; doing it in production multi-tenant is a security incident. Add the layer before the first tenant.

## Minimal reference loader

A complete loader fits in <200 lines of Python. See the matching reference impl in [`agent-deployments/docs/capabilities/`](https://github.com/jagguvarma15/agent-deployments/tree/main/docs/capabilities/) (specifically the `mcp.*` and skill-loader capability docs once they land) for the production-shape version that wires in sandboxing, tracing, and the grant policy.

## See also

- [`overview.md`](./overview.md) — headline concept and tradeoffs.
- [`design.md`](./design.md) — component diagrams and failure modes.
- [`evolution.md`](./evolution.md) — how skills grew out of inline prompt instructions.
- [`observability.md`](./observability.md) — what to trace per skill invocation.
- [`cost-and-latency.md`](./cost-and-latency.md) — sizing the registry, the matcher, and the body budget.
- [`prompts/skill-loader.md`](./prompts/) — example LLM judge prompt template.
