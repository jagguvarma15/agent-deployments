# Cross-cutting: Prompt management — versioning, registry, A/B, rollback

**Concern:** How the prompt strings recipes ship in `## Prompt Specifications` are versioned, registered, A/B tested, and rolled back in production.
**Lives in:** A prompt registry (Langfuse, LangSmith, or a flat-file `prompts/<role>.md` tree with git as the registry). The recipe's `## Prompt Specifications` body documents the *contract*; the registry stores the *string*.
**Related:** [`model-routing.md`](model-routing.md), [`eval-data.md`](eval-data.md), [`observability.md`](observability.md), [`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md), [`../capabilities/obs/langfuse.md`](../capabilities/obs/langfuse.md), [`../capabilities/obs/langsmith.md`](../capabilities/obs/langsmith.md).

Recipes ship a `## Prompt Specifications` section with the literal system prompt and design rationale. This doc is for the next step: turning that seed into a discipline you can roll back, A/B against, and re-eval against without losing track of which prompt produced which result.

## 1. What this is for

| Purpose | In scope | Out of scope |
|---------|----------|--------------|
| Versioning the prompt string so a regression is attributable | yes | |
| Registering prompts in a shared store readable from production + CI + eval | yes | |
| A/B routing a fraction of traffic onto a new version with deterministic keying | yes | |
| Rolling back instantly when a quality, latency, or schema regression hits | yes | |
| Linking eval rows to the prompt version they were authored against | yes | |
| Prompt engineering technique (chain of thought, few-shot framing, role priming) | | no — that's prompt-engineering literature, not registry mechanics |
| Storing few-shot examples as separate registry entries | | no — keep examples inside the prompt body until you have enough to merit their own discipline |
| Synthesizing prompts via meta-LLM | | no — separate concern; an LLM-authored prompt still goes through the lifecycle here |

Prompt management is the operational layer wrapping the prompt string. It tells you how to change a prompt without breaking the agent.

## 2. Anatomy of a versioned prompt

A registered prompt is a tuple:

```
(name, version, body, model_hint, labels, registered_at)
```

| Field | Type | Purpose |
|-------|------|---------|
| `name` | string | Stable across versions. Matches the recipe role (e.g. `intake`, `classifier`, `orchestrator`). One name per `Prompt Specifications` block in a recipe. |
| `version` | int | Monotone integer. Never reused. Increments on every published change. |
| `body` | string | The prompt content. Includes the system-prompt template plus any inline variable placeholders (`{{user_message}}`, `{{tools_summary}}`). |
| `model_hint` | string | The `model_hint` the prompt was authored against (`haiku` / `sonnet` / `opus`). Read alongside [`model-routing.md`](model-routing.md) when picking the runtime model. |
| `labels` | list[string] | Routing labels. `production`, `canary`, `experiment:routing-v2`, `dev`. The runtime resolves by label, not by version, so swapping versions is one API call. |
| `registered_at` | ISO 8601 | Frozen at publication. Surfaces in trace and eval row metadata so audits can correlate behavior to a specific publish event. |

Two invariants:

- **Body is immutable once published.** Never edit a published version. Publish a new version and swap the label. This is the rollback story; without immutability, "roll back to v3" doesn't mean anything.
- **Labels are mutable, versions aren't.** A label like `production` points at exactly one version at a time. Reassigning the label is the deploy / rollback primitive.

## 3. Registry options

Pick one registry per project. Don't shard across registries — the rollback playbook assumes one source of truth.

| Registry | Integration ergonomics | A/B routing | Rollback | Latency | When to pick |
|----------|------------------------|-------------|----------|---------|--------------|
| **Langfuse** (`langfuse.get_prompt(...)`) | First-class SDK, hosted UI, version diff view | Yes — labels (`production`, `canary`) and arbitrary tags | Label swap is one API call | ~50–150 ms cold, ~5 ms cached | Already running Langfuse for observability ([`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md), [`../capabilities/obs/langfuse.md`](../capabilities/obs/langfuse.md)); want one tool covering tracing + prompts. |
| **LangSmith Hub** (`client.pull_prompt(...)` / `client.push_prompt(...)`) | First-class SDK, hosted UI, tightly coupled to LangChain tracing | Yes — tags + commit hashes | Tag re-point or hash-pin in code | ~50–150 ms cold, ~5 ms cached | Already running LangSmith for tracing; downstream eval flows use LangSmith datasets. |
| **In-repo flat files** (`prompts/<role>.md`, git as registry) | Zero SDK; git history is the version log | Manual — feature flag in the runtime picks a path | Revert commit + redeploy | None — read from disk on start | Single-team project; don't want the SDK dependency; deploy cadence is fast enough that "ship a new version" is a code change. |

The flat-file option is recipe-side-friendly: the prompt body lives next to the code that uses it, and the recipe's `## Prompt Specifications` section is the human-readable export of the same string. It does not give you the runtime label-swap primitive — rollback is a code revert + redeploy — so reach for it only when redeploy cycles measure in minutes, not hours.

## 4. Versioning discipline

Monotone integers, not semantic versions. Reasoning:

- Prompt strings don't have stable consumer-side APIs; semantic versioning's "major / minor / patch" doesn't carry meaning. Every change risks behavior drift.
- Monotone integers make queries simple: `version > 4`, `latest published`, `count(versions) where name='intake' and registered_at > '2026-06-01'`.
- Tooling on top of integers is straightforward — the registry's "previous version" is `v - 1`.

Bumping the version:

- **Bump on any body change.** A single-word edit is still a bump. The prompt is a behavior contract; even a punctuation tweak can move the score.
- **Bump on `model_hint` change.** The same string against Haiku and Opus produces different outputs. Pinning the hint in the registry entry lets the runtime pick the matched model and lets eval rows attribute scores to the (prompt × model) pair.
- **Do not bump on label change.** Labels move across versions; that's the point.

Recipe linkage:

- The recipe's `## Prompt Specifications` section names the prompt and documents the contract (variables in, output schema out).
- The recipe's `frontmatter` does not pin a version — pinning belongs in the runtime config (`PROMPT_LABEL=production`) so the recipe stays portable across registries.
- The recipe's body shows the *current* prompt string verbatim. When a new version ships, the recipe is updated in the same PR that publishes the version. A drift detector in CI can grep the recipe body against the registry's `label=production` body to catch divergence.

## 5. Langfuse integration

Langfuse provides `create_prompt` / `get_prompt` / `update_prompt_labels`. Minimal Python:

```python
from langfuse import Langfuse

lf = Langfuse()  # reads LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from env

# Publish a new version. Labels carry routing.
lf.create_prompt(
    name="intake",
    prompt="You are an intake agent. Classify {{event_type}}...",
    config={"model_hint": "sonnet", "registered_at": "2026-06-06T14:00:00Z"},
    labels=["canary"],
)

# Read at runtime — label-resolved, cached client-side per Langfuse's docs.
prompt = lf.get_prompt(name="intake", label="production")
system_message = prompt.compile(event_type="reservation.cancelled")
```

TypeScript:

```typescript
import { Langfuse } from "langfuse";

const lf = new Langfuse();

await lf.createPrompt({
  name: "intake",
  prompt: "You are an intake agent. Classify {{event_type}}...",
  config: { model_hint: "sonnet" },
  labels: ["canary"],
});

const prompt = await lf.getPrompt("intake", undefined, { label: "production" });
const systemMessage = prompt.compile({ event_type: "reservation.cancelled" });
```

Langfuse's client caches `get_prompt` results in-process, so the steady-state cost is ~5 ms; a cold-cache call is one HTTPS round trip. Pre-warm at process start (call `get_prompt` for every label your runtime will read) so the first user request doesn't pay the cold cost.

For the SDK versions, anchor against [`../capabilities/obs/langfuse.md`](../capabilities/obs/langfuse.md) — that capability doc names the canonical pin and is updated when Langfuse's prompt-management API surface evolves.

## 6. LangSmith integration

LangSmith Hub exposes the same primitives under different names. Minimal Python:

```python
from langsmith import Client

client = Client()  # reads LANGSMITH_API_KEY, LANGSMITH_ENDPOINT from env

# Publish — produces a commit hash.
client.push_prompt(
    "intake",
    object="You are an intake agent. Classify {event_type}...",
    tags=["canary"],
)

# Read at runtime — by tag (mutable) or commit hash (immutable).
prompt = client.pull_prompt("intake:production")  # tag form
# Or pin: client.pull_prompt("intake:c4f6a2e9...")  # commit hash form
```

LangSmith's prompt strings use LangChain's `{variable}` (single-brace) template style, in contrast to Langfuse's `{{variable}}`. The runtime that resolves the prompt must apply the right substitution shape — store the `template_style` in the registry config to avoid silent shape mismatches.

A defensive cross-link for SDK versions: until a dedicated `docs/stack/langsmith.md` lands (PR #45 punted on the doc), [`../capabilities/obs/langsmith.md`](../capabilities/obs/langsmith.md) is the canonical pin and contract reference.

## 7. A/B routing

A/B routing belongs in the runtime, not the registry. The registry stores prompts and labels; the runtime picks which label to read based on the request.

The same `(tenant_id, request_id)` deterministic key [`model-routing.md`](model-routing.md) uses is the right primitive here:

```python
import hashlib

def pick_label(tenant_id: str, request_id: str, experiment: str | None = None) -> str:
    """Deterministic A/B between production and experiment labels.

    Same (tenant_id, request_id) always lands in the same arm — eval replays
    and post-hoc analyses can attribute outcomes correctly.
    """
    if experiment is None:
        return "production"
    h = hashlib.sha256(f"{experiment}:{tenant_id}:{request_id}".encode()).digest()
    bucket = int.from_bytes(h[:4], "big") / 0xFFFFFFFF  # [0, 1)
    return experiment if bucket < ENROLLMENT_FRACTION[experiment] else "production"

ENROLLMENT_FRACTION = {"experiment:routing-v2": 0.05}
```

Then in the per-request path:

```python
label = pick_label(tenant_id, request_id, experiment="experiment:routing-v2")
prompt = lf.get_prompt(name="intake", label=label)
# Tag the trace with the resolved label so eval + analysis can group on it.
trace.update(metadata={"prompt_label": label, "prompt_version": prompt.version})
```

Three invariants:

- **Deterministic keying.** A given `(tenant_id, request_id)` lands in the same arm across retries and replays. Without this, post-hoc analyses (compare quality on the experiment arm vs. control) leak.
- **Record the resolved label and version on the trace.** Downstream analytics need both — without the version, "the experiment arm regressed" can't be attributed to a specific publish.
- **Enrollment fractions live in code (or a feature flag), not in the registry.** The registry's job is to serve the right string for a given label; the runtime decides which label to ask for.

## 8. Rollback playbook

Three concrete scenarios. Each has a signal, a decision rule, and an exact mechanic.

### 8a. Latency regression

- **Signal.** P95 LLM-call latency for the role exceeded the SLO band ([`model-routing.md`](model-routing.md) §latency budget) within 5 minutes of a publish.
- **Decision rule.** If the new version's prompt is materially longer (token count > 1.2× the previous), or if a new field in the model's expected output adds round-trips (structured output that triggers re-prompts), roll back.
- **Mechanic.** Move the `production` label from `vN` back to `vN-1`. Langfuse: `lf.update_prompt_labels(name, version=N-1, labels=["production"])`. LangSmith: re-tag. Cached clients pick up the new resolution within the cache TTL (typically 60–300 s); to force immediate rollback, also bump a `prompt_cache_bust` env var the runtime reads.

### 8b. Quality regression

- **Signal.** Eval pass-rate on the recipe's golden set dropped below the recipe-declared floor; or production-trace LLM-as-judge scores dropped below the alert threshold ([`eval-data.md`](eval-data.md) §evaluator strategies).
- **Decision rule.** A quality regression on golden cases authored against the previous prompt version is a roll-back; a quality regression authored against the new version means the eval set needs re-curation, not the prompt revert.
- **Mechanic.** Same label-swap as latency. Additionally, re-run the eval with both `prompt_version=N` and `prompt_version=N-1` on the same dataset — the diff explains the regression.

### 8c. Schema-mismatch outage

- **Signal.** Production traces show a sudden spike in `tool_call` or structured-output parse failures correlating with a publish.
- **Decision rule.** Schema-mismatch is always a roll-back. The new prompt cannot stay in production while emitting unparseable output, even if golden-set quality is fine.
- **Mechanic.** Label swap, then open an issue against the prompt author. Common cause: the prompt's output instructions drifted from the schema declared in the recipe's `output_type`; the recipe and prompt must be re-aligned in the same PR.

## 9. Eval integration

Every row in `eval/dataset.jsonl` carries the prompt version it was authored against:

```json
{
  "id": "intake-014",
  "input": {"event_type": "reservation.cancelled", "actor": "platinum-tier"},
  "expected": {"decision": "rebook"},
  "metadata": {
    "prompt_version": 7,
    "prompt_label_at_authoring": "canary",
    "frozen_at": "2026-05-30"
  }
}
```

Re-running the eval against a new version produces a comparable score. Three invariants:

- **Score the new prompt against the eval rows authored at its version, not earlier ones.** Rows authored against v3 with prompt v5 measure drift, not quality. Drift can be intentional (the new prompt changed behavior on purpose) — `eval-data.md`'s drift detection is the right framing.
- **Carry `prompt_label_at_authoring` so re-enrollment doesn't accidentally compare against the production arm of an old experiment.**
- **Re-author the eval row when the prompt's contract changes** (a new output field, a renamed variable). Old rows are archived, not edited — same immutability principle the registry uses.

Cross-link to [`eval-data.md`](eval-data.md) §anatomy-of-a-row: the `prompt_version` field is one of the recommended metadata keys for any recipe whose dataset is non-trivial.

## 10. Anti-patterns

- **String literals in code.** A prompt baked into a Python triple-quoted string kills the entire discipline below. Even if you "just want to ship something," wrap it in a stub `get_prompt(name)` that returns the literal — making the indirection visible is the precondition for ever versioning it.
- **Regenerating prompts via meta-LLM without recording the change.** If a tool synthesizes a new prompt, the synthesis must publish a new registry version with metadata identifying the synthesis run (model, parameters, source). Otherwise the agent's behavior changed and no audit trail explains why.
- **Judging new prompts against old eval rows.** Comparing v5's output to expectations authored against v3 measures drift, not quality. The right framing is "drift expected because behavior intentionally changed" or "regression because behavior unintentionally changed" — never "quality went down."
- **A/B without deterministic keying.** Random-per-call routing makes retries land in different arms, which makes post-hoc analysis impossible. Always key on `(tenant_id, request_id)` or an equivalent stable pair.
- **Rolling back by editing the published version.** Defeats the audit trail and breaks replays. Publish a corrected version and swap the label.
- **Sharding across registries.** Half the prompts in Langfuse, half in LangSmith. Rollback playbooks assume one source of truth; a registry split means rollback paths fork and operational complexity compounds without payoff.
- **No cold-cache pre-warm.** Forcing the first request after deploy to pay the SDK's cold-cache HTTPS round trip elevates user-visible latency. Pre-warm at process start.

## See also

- [`model-routing.md`](model-routing.md) — per-role model selection, fallback chains, and the deterministic-keying primitive A/B routing reuses.
- [`eval-data.md`](eval-data.md) — golden-set curation, drift detection, and the `metadata.prompt_version` row field this doc references.
- [`observability.md`](observability.md) — trace shape; record `prompt_label` and `prompt_version` on every trace.
- [`../stack/tracing-langfuse.md`](../stack/tracing-langfuse.md) — Langfuse setup; the prompts API piggybacks on the same client.
- [`../capabilities/obs/langfuse.md`](../capabilities/obs/langfuse.md) — Langfuse capability doc; canonical SDK pin.
- [`../capabilities/obs/langsmith.md`](../capabilities/obs/langsmith.md) — LangSmith capability doc; canonical SDK pin.
