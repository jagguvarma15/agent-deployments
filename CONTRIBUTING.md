# Contributing to agent-deployments

Thank you for your interest in contributing! This guide covers how to add a new
prototype, submit a stack swap, or improve existing code.

## Getting started

1. Fork and clone the repo
2. Ensure you have Docker, `uv` (Python), and `pnpm` (TypeScript) installed
3. Pick a prototype and run it locally to verify your setup:
   ```bash
   cd prototypes/customer-support-triage/python
   cp .env.example .env
   make up
   ```

## Types of contributions

### Bug fixes and improvements to existing prototypes

1. Open an issue describing the bug or improvement
2. Fork, branch (`fix/<short-description>` or `improve/<short-description>`), and fix
3. Ensure `make test PROTOTYPE=<name>` and `make lint PROTOTYPE=<name>` pass
4. Submit a PR referencing the issue

### Stack swaps

Want to document how to swap a default pick (e.g., Qdrant to Pinecone)?

1. Use the `stack-swap` issue template
2. Add documentation to the relevant prototype's `docs/swaps.md`
3. If the swap requires code changes, include those in the same PR
4. Categorize the swap: single-file, multi-file, or architectural

### New prototypes

New prototypes must:

1. Use the `new-prototype` issue template for discussion first
2. Map to a pattern from [`agent-blueprints`](https://github.com/jagguvarma15/agent-blueprints)
3. Implement **both** Python and TypeScript tracks
4. Meet all acceptance criteria (see below)
5. Start from the `prototypes/_template/` directory

## Acceptance criteria

Before a PR is merged, every prototype must satisfy:

- [ ] Both `python/` and `typescript/` tracks implemented
- [ ] `make up PROTOTYPE=<name> TRACK=python` works with only Docker and env vars
- [ ] `make up PROTOTYPE=<name> TRACK=typescript` works similarly
- [ ] `curl localhost:PORT/health` returns 200
- [ ] Example curl from README executes and returns a valid response
- [ ] Langfuse UI shows a trace with all spans
- [ ] `make test PROTOTYPE=<name>` passes
- [ ] `make eval PROTOTYPE=<name>` runs and reports metrics
- [ ] `make security PROTOTYPE=<name>` passes (no criticals)
- [ ] README has: Blueprint Map, Stack table, Architecture diagram, Run instructions, API, Observability, Evaluation, Swaps link, Py-vs-TS reflection
- [ ] Every secret lives in `.env.example` with a comment
- [ ] Docker image <200 MB (Python) / <150 MB (TypeScript)
- [ ] CI green across both tracks

## Code style

- **Python**: formatted and linted with `ruff`
- **TypeScript**: formatted and linted with `Biome`
- Run `make lint PROTOTYPE=<name>` before submitting

## Commit messages

Use concise, descriptive commit messages:
- `add: <prototype-name> python track`
- `fix: rate limiter race condition in common/python/ratelimit`
- `docs: update stack.md with Qdrant version bump`

## PR checklist

- [ ] I have read the contributing guide
- [ ] Both language tracks are included (for new prototypes)
- [ ] Tests pass locally
- [ ] I have updated relevant documentation
- [ ] I have not committed secrets or API keys

## Questions?

Open a discussion or issue. We're happy to help scope contributions before you invest time building.
