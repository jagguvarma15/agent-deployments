---
id: core.tracing
kind: core
implements:
  port: core
  interface_version: "1.0"
layer: agent
provides: [tracing, spans]
env_vars: []
docker: null
probe: null
bootstrap_step: null
provisioning_time: instant
cost_tier: free
card:
  name: Tracing
  description: "Structured span emission around model and tool calls — request id, model, token counts, duration — as redacted JSONL with no backend required. The T3 production substrate; obs.* backends export what this emits."
  capabilities_provided: [tracing, spans]
  required_credentials: []
emit_files:
  - source: templates/tracing/tracing.py
    dest: agent/tracing.py
deploy_configs: []
docs: |
  Emits agent/tracing.py: a span() context manager and a model_call() helper
  that append one redacted JSON line per unit of work to TRACE_PATH (default
  .agent/trace.jsonl; the sentinel value "stdout" prints instead;
  TRACE_ENABLED=0 disables). Do NOT reinvent the emitter — import it:
  `from agent.tracing import model_call, span`. Bracket every Anthropic API
  call with model_call(model) and set input_tokens / output_tokens on the
  yielded dict from the response usage; bracket tool invocations and retrieval
  steps with span(name, **attrs). The .agent/trace.jsonl stream is runtime
  output — gitignore it (the scaffold does this by default). This capability
  is backend-free by design: obs.langfuse / obs.langsmith / obs.grafana-stack
  are exporters layered on top of this stream, not replacements for it.
tags: [core, tracing, spans, observability, production]
when_to_load: "recipe tier is T3 or higher (the tier preset seeds core.tracing)"
---

# Core: Tracing

The production substrate emitted at the **T3** tier. Every model call and tool
invocation is bracketed by a span recording what ran, how long it took, and
what it cost (token counts) — as an append-only, secret-redacted JSONL stream
that needs no backend, no credentials, and no network. Production tier means
traces exist; where they are shipped is a separate, optional decision.

## Relationship to the obs backends

`core.tracing` is deliberately backend-free. The observability capabilities
(`obs.langfuse`, `obs.langsmith`, `obs.grafana-stack`) are **exporters layered
on top** of the span stream this module emits — they consume it, they do not
replace it. Picking a backend in the scaffold's observability step adds the
exporter; dropping the backend later still leaves the local trace intact.

## Emitted files

| File | Role |
|---|---|
| `agent/tracing.py` | `span()` context manager + `model_call()` helper + the redacted JSONL emitter. Standard library only. |

The copier never overwrites a file the model emitted at the same path, so a
recipe can specialize the emitter while inheriting the contract.

## Wiring

```python
from agent.tracing import model_call, span

with span("retrieve", query_id=qid):
    docs = store.search(query)

with model_call("claude-opus-4-8") as call:
    response = client.messages.create(...)
    call["input_tokens"] = response.usage.input_tokens
    call["output_tokens"] = response.usage.output_tokens
```

An exception inside a span marks it `error` (with the exception type) and
re-raises — tracing never swallows failures, and the emitter never raises
(a full disk silently drops the span rather than taking the agent down).

## Environment

Both variables are optional with safe defaults — they are configuration, not
credentials, so they carry no entry in the env contract:

| Variable | Default | Meaning |
|---|---|---|
| `TRACE_ENABLED` | `1` | `0` / `false` turns every span into a no-op. |
| `TRACE_PATH` | `.agent/trace.jsonl` | Where spans land; `stdout` prints them instead. |

When pairing with the T2 step log, pointing `TRACE_PATH` into the active run
directory (`.agent/runs/<run_id>/trace.jsonl`) keeps a run's state and its
spans side by side.

## Redaction

Every string attribute passes the same conservative secret-shaped patterns as
the step log (`sk-ant-`, generic `sk-`, bearer tokens, URL userinfo, GitHub
PATs) before touching disk or stdout. A false positive on legitimate text is
far cheaper than a single leaked credential.
