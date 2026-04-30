# Reference: CI Pipeline Template

GitHub Actions workflow with change detection, dual-track testing, and security scanning.

## Key design decisions

- **Change detection** — only tests prototypes that actually changed, saving CI minutes
- **Common/ triggers all** — if shared libraries change, all prototypes are tested
- **Three-tier testing** — unit on every PR, integration + eval on main only (saves API costs)
- **Exit code 5** — "no tests collected" is treated as success
- **Security scanning** — Promptfoo red-team runs on main only with `continue-on-error: true`
- **Concurrency** — cancels in-progress runs on the same branch

## Full workflow

```yaml
name: CI

on:
  push:
    branches: [main]
    paths:
      - "prototypes/**"
      - "common/**"
  pull_request:
    branches: [main]
    paths:
      - "prototypes/**"
      - "common/**"

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # ---------------------------------------------------------------------------
  # Detect which prototypes changed (excludes _template)
  # ---------------------------------------------------------------------------
  changes:
    runs-on: ubuntu-latest
    outputs:
      prototypes: ${{ steps.detect.outputs.prototypes }}
      has_prototypes: ${{ steps.detect.outputs.has_prototypes }}
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - id: detect
        name: Detect changed prototypes
        run: |
          if [ "${{ github.event_name }}" = "push" ]; then
            BASE=${{ github.event.before }}
          else
            BASE=${{ github.event.pull_request.base.sha }}
          fi

          # Find changed prototype directories (exclude _template)
          CHANGED=$(git diff --name-only "$BASE" HEAD \
            | grep '^prototypes/' \
            | cut -d'/' -f2 \
            | grep -v '^_template$' \
            | sort -u \
            | jq -R -s -c 'split("\n") | map(select(length > 0))')

          # If common/ changed, run all real prototypes
          if git diff --name-only "$BASE" HEAD | grep -q '^common/'; then
            CHANGED=$(ls prototypes/ 2>/dev/null | grep -v '^_template$' | jq -R -s -c 'split("\n") | map(select(length > 0))')
          fi

          echo "prototypes=$CHANGED" >> "$GITHUB_OUTPUT"

          # Check if there are actual prototypes to test
          if [ "$CHANGED" = "[]" ] || [ "$CHANGED" = '[""]' ] || [ -z "$CHANGED" ]; then
            echo "has_prototypes=false" >> "$GITHUB_OUTPUT"
          else
            echo "has_prototypes=true" >> "$GITHUB_OUTPUT"
          fi

  # ---------------------------------------------------------------------------
  # Python track
  # ---------------------------------------------------------------------------
  python:
    needs: changes
    if: needs.changes.outputs.has_prototypes == 'true'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        prototype: ${{ fromJson(needs.changes.outputs.prototypes) }}
    defaults:
      run:
        working-directory: prototypes/${{ matrix.prototype }}/python
    steps:
      - uses: actions/checkout@v4

      - name: Check python track exists
        id: check
        run: test -f prototypes/${{ matrix.prototype }}/python/pyproject.toml
        working-directory: ${{ github.workspace }}
        continue-on-error: true

      - name: Install uv
        if: steps.check.outcome == 'success'
        uses: astral-sh/setup-uv@v4
        with:
          version: "0.5.10"

      - name: Set up Python
        if: steps.check.outcome == 'success'
        run: uv python install 3.12

      - name: Install dependencies
        if: steps.check.outcome == 'success'
        run: uv sync

      - name: Lint
        if: steps.check.outcome == 'success'
        run: uv run ruff check .

      - name: Type check
        if: steps.check.outcome == 'success'
        run: uv run ruff check . --select=ANN
        continue-on-error: true

      - name: Unit tests
        if: steps.check.outcome == 'success'
        run: uv run pytest tests/unit -v

      - name: Integration tests (main only)
        if: steps.check.outcome == 'success' && github.ref == 'refs/heads/main'
        run: uv run pytest tests/integration -v || test $? -eq 5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Eval suite (main only)
        if: steps.check.outcome == 'success' && github.ref == 'refs/heads/main'
        run: uv run pytest tests/evals -v || test $? -eq 5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Docker build
        if: steps.check.outcome == 'success'
        run: docker build -f prototypes/${{ matrix.prototype }}/python/Dockerfile -t agent-deployments/${{ matrix.prototype }}-python .
        working-directory: ${{ github.workspace }}

  # ---------------------------------------------------------------------------
  # TypeScript track
  # ---------------------------------------------------------------------------
  typescript:
    needs: changes
    if: needs.changes.outputs.has_prototypes == 'true'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        prototype: ${{ fromJson(needs.changes.outputs.prototypes) }}
    defaults:
      run:
        working-directory: prototypes/${{ matrix.prototype }}/typescript
    steps:
      - uses: actions/checkout@v4

      - name: Check typescript track exists
        id: check
        run: test -f prototypes/${{ matrix.prototype }}/typescript/package.json
        working-directory: ${{ github.workspace }}
        continue-on-error: true

      - uses: pnpm/action-setup@v4
        if: steps.check.outcome == 'success'
        with:
          version: 9

      - uses: actions/setup-node@v4
        if: steps.check.outcome == 'success'
        with:
          node-version: 22

      - name: Install dependencies
        if: steps.check.outcome == 'success'
        run: pnpm install

      - name: Lint
        if: steps.check.outcome == 'success'
        run: pnpm run lint

      - name: Type check
        if: steps.check.outcome == 'success'
        run: pnpm run typecheck

      - name: Unit tests
        if: steps.check.outcome == 'success'
        run: pnpm run test:unit

      - name: Integration tests (main only)
        if: steps.check.outcome == 'success' && github.ref == 'refs/heads/main'
        run: pnpm run test:integration
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Eval suite (main only)
        if: steps.check.outcome == 'success' && github.ref == 'refs/heads/main'
        run: pnpm run test:eval
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Docker build
        if: steps.check.outcome == 'success'
        run: docker build -t agent-deployments/${{ matrix.prototype }}-typescript .

  # ---------------------------------------------------------------------------
  # Security scan (Promptfoo)
  # ---------------------------------------------------------------------------
  security:
    needs: changes
    if: needs.changes.outputs.has_prototypes == 'true' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        prototype: ${{ fromJson(needs.changes.outputs.prototypes) }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install Promptfoo
        run: npm install -g promptfoo

      - name: Run security scan (Python eval config)
        run: promptfoo redteam run --config prototypes/${{ matrix.prototype }}/python/eval/promptfoo.yaml
        if: hashFiles(format('prototypes/{0}/python/eval/promptfoo.yaml', matrix.prototype)) != ''
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        continue-on-error: true

      - name: Run security scan (TypeScript eval config)
        run: promptfoo redteam run --config prototypes/${{ matrix.prototype }}/typescript/eval/promptfoo.yaml
        if: hashFiles(format('prototypes/{0}/typescript/eval/promptfoo.yaml', matrix.prototype)) != ''
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        continue-on-error: true
```

## Adapting for your project

- Replace the `changes` job with your own path detection or remove it for a single-agent repo
- Adjust `working-directory` to match your project structure
- Add deployment steps after the test jobs if needed
- Add `ANTHROPIC_API_KEY` to your GitHub repository secrets
