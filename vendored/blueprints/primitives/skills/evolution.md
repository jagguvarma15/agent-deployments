# Skills — Evolution

> How skills grew out of [`Tool Use`](../tool_use/overview.md) and inline prompt instructions, and what's still missing.

## The arc

Agents started as monolithic prompts. The entire procedure — how to think, what tools exist, when to use them, how to format outputs — lived in one giant system prompt that grew as the agent's job grew. This worked at toy scale and broke fast at production scale:

1. **Phase 1 — Inline prompt instructions.** Procedures lived as bullet-pointed sections inside the system prompt: "When the user asks X, do Y, Z, then format as JSON with keys A, B." Easy to author, easy to ship, *very* expensive in tokens (every turn paid for every procedure whether or not it applied), and very hard to maintain when the procedure list grew past ~5 entries.

2. **Phase 2 — Tool catalogs ([Tool Use](../tool_use/overview.md)).** The tool-use pattern abstracted *capabilities* — "here are the functions you can call." This was the right shape for access (the agent gets a tool to search the web) but the wrong shape for procedure (the agent didn't know *how* to use the search results in your domain). Per-tool descriptions ballooned with "when you call this, do X; the result will be in format Y; combine with tool Z" — procedural knowledge bleeding into tool docs.

3. **Phase 3 — Skills (you are here).** Procedural knowledge gets its own primitive: file-based, discovered at runtime, loaded on demand. Tools stay tools (access). MCP servers stay MCP servers (remote access). Skills are the missing leg.

The shift in 2025-2026 came from three forces:

- **Context window economics.** Even with 200K+ context windows, paying tokens for unused procedures every turn is silly. Lazy loading is the only sustainable answer.
- **Anthropic's `SKILL.md` convention.** Anthropic shipped a concrete file-based skill format; it caught on because folder-shaped artifacts compose with Git workflows.
- **Multi-agent + MCP.** Once agents started delegating to other agents and calling remote tools, the question "what does each agent know how to do, *specifically in this org*?" became sharp. Skills answer it.

## What skills inherit from Tool Use

Skills are the [`Tool Use`](../tool_use/overview.md) pattern with two key additions:

| | Tool Use | Skills |
|---|---|---|
| Catalog | Tool registry. | Tool registry + skill registry. |
| Loading | All tool descriptions loaded into context every turn. | Skill descriptions loaded; bodies only on selection. |
| Authoring | Tool authors write Python/TS functions + JSON-schema descriptions. | Skill authors write markdown + optional scripts. |
| Discoverability | LLM picks tools from the catalog at each step. | LLM picks skills via two-stage matcher (keyword + judgment). |
| Composability | Tools compose via the agent's reasoning loop. | Skills compose with tools — skills *use* tools as building blocks. |

A clean way to think about it: tools answer "what can I do?"; skills answer "given what I can do, what's the right procedure for *this* task in *this* environment?"

## What's still being worked out

Three open design questions in the wider ecosystem as of 2026:

### 1. Cross-skill dependencies

When skill A's procedure says "first run skill B to get X, then use X to do Y," the matcher has no way to enforce that ordering. Today this is hand-waved ("the agent will figure it out"). Several proposals are circulating:

- **Skill graphs** — explicit `requires_skill: [other-skill-id]` in frontmatter; matcher pulls in prerequisites automatically.
- **Skill compositions** — bundle related skills into a "skillset" that loads together.
- **Subagent dispatch** — dependencies promote to A2A delegation: "this skill needs that capability; spin up a subagent that has it."

None of these are conventions yet.

### 2. Skill versioning + drift

A skill written six months ago against a since-changed MCP server is silently broken. Versioning helps catch this at boot if `requires:` declares MCP server versions, but the convention isn't universal. The likely converging pattern: per-skill canned-input tests in CI ("run this skill against the canonical example; assert the output matches the recorded baseline").

### 3. Untrusted skills

The natural progression from "skills as code in your repo" to "skills published by third parties" raises real security questions: malicious skill bodies (prompt injection), malicious scripts (host compromise), malicious metadata (registry confusion). Sandbox + grant policy are the architectural answers; convention for *signed* skill bundles + a registry of trusted publishers is the missing operational answer.

## Why this pattern is its own thing now

You could argue skills are "just a flavor of tool use." Two reasons they earn their own pattern entry:

1. **The loading model is fundamentally different.** Tool catalogs are eagerly loaded. Skill catalogs are lazily loaded. That's not a polish detail; it's the load-bearing economic difference that lets you ship 100s of skills.

2. **The authoring boundary is different.** Tools are written by engineers (Python/TS). Skills are written by anyone who can write markdown (PMs, ops, domain experts, AI engineers). That difference unlocks who can extend the agent without changing core code.

## Looking forward

Likely directions over the next year:

- **Skill marketplaces.** Public registries of skills the way npm exists for packages. With all the same caveats.
- **Hybrid skill/tool primitives.** "Skill that exposes itself as an MCP server" so other agents can discover it via standard protocols.
- **Skill-aware routing.** Routers that pre-classify queries to skill domains before the matcher runs, scaling registries past the ~1k mark.

For now, the pattern is mature enough to ship and immature enough that conventions are still settling. Adopt with eyes open.

## See also

- [`overview.md`](./overview.md) — the headline concept.
- [`primitives/tool_use/evolution.md`](../tool_use/evolution.md) — the pattern this evolved from.
- [`foundations/agent-protocols.md`](../../foundations/agent-protocols.md) — how skills, MCP, and A2A are the three connectivity primitives.
