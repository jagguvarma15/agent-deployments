# Capability templates

Some capabilities ship file trees alongside their markdown. The scaffold's copier walks the `emit_files:` glob declared in each capability's frontmatter and copies the matching files into the generated project at the declared `dest:` path.

## Where they live

Templates are co-located with their capability markdown, under a `templates/` sibling directory:

```
docs/capabilities/<kind>/<name>.md
docs/capabilities/<kind>/templates/<name>/...
```

Examples:

| Capability | Template tree | Emit destination (in generated project) |
|------------|---------------|------------------------------------------|
| `host.vercel` | `host/templates/vercel/` | `./` (vercel.json, .vercelignore) |
| `host.railway` | `host/templates/railway/` | `./` (railway.json, .railwayignore) |
| `host.fly` | `host/templates/fly/` | `./` (fly.toml, .dockerignore) |
| `frontend.nextjs-chat` | `frontend/templates/nextjs-chat/` | `frontend/` (full Next.js scaffold) |
| `frontend.streamlit` | `frontend/templates/streamlit/` | `frontend/` (Streamlit app) |
| `obs.grafana-stack` | `obs/templates/grafana-stack/` | `ops/grafana/` (prometheus.yml, tempo.yaml, dashboards) |
| `eval.promptfoo` | `eval/templates/promptfoo/` | `evals/` (promptfooconfig.yaml, cases.yaml) |

## They are not standalone code

Templates contain placeholder tokens that the scaffold's emitter rewrites during project generation:

- `REPLACE_WITH_<NAME>` — literal-string substitution (e.g. `REPLACE_WITH_FLY_APP_NAME` in `fly.toml`)
- `@<secret-name>` — Vercel secret-reference syntax (resolved against the Vercel project's stored secrets)
- Unresolved env-var references (e.g. `$PORT` in Railway's start command) — interpreted by the runtime, not the scaffold

Browsing a template tree as a standalone project will show validation errors — that's expected.

Do not lint, type-check, or run templates as if they were production code. The repo's CI gates only verify that declared `emit_files:` source paths resolve to existing files; runtime correctness lives in the generated project, not here.

## `emit_files:` contract

Each capability's frontmatter declares which files to emit:

```yaml
emit_files:
  - source: templates/<name>/path/to/file
    dest: relative/path/in/project
```

- **`source`** is relative to the capability's directory (not repo root). `templates/<name>/vercel.json` resolves to `docs/capabilities/<kind>/templates/<name>/vercel.json`.
- **`dest`** is relative to the generated project's root.
- **Globs** (`**`, `*`) are supported in `source` for tree-copy:

  ```yaml
  emit_files:
    - source: templates/<name>/**
      dest: frontend/
  ```

  The copier preserves directory structure under `dest`.

## Adding a template

1. Add the capability markdown under `docs/capabilities/<kind>/<name>.md` (per the schema in [`README.md`](README.md)).
2. Create the template tree under `docs/capabilities/<kind>/templates/<name>/`.
3. Declare each emit path in the capability's `emit_files:` frontmatter.
4. Verify the `source:` path resolves:

   ```bash
   for f in $(find docs/capabilities -name '*.md' -not -name 'README.md' -not -name 'TEMPLATES.md'); do
     python3 -c "import re, pathlib, yaml
   text = pathlib.Path('$f').read_text()
   fm_match = re.search(r'^---\n(.*?)\n---', text, re.S)
   if not fm_match: exit()
   fm = yaml.safe_load(fm_match.group(1))
   for entry in fm.get('emit_files') or []:
       src = entry.get('source')
       if not src: continue
       p = pathlib.Path('$f').parent / src.split('**')[0].rstrip('/')
       if not p.exists() and not list(pathlib.Path('$f').parent.glob(src)):
           print(f'UNRESOLVED: {src} in $f')
   "
   done
   ```

## When NOT to ship a template

Don't declare `emit_files` for content the generated project can produce on its own from the LLM context (e.g. a `Dockerfile` that the LLM emits is preferable to a stub the scaffold copies — the LLM's specialization wins).

Templates are right for content that's:

- **Provider-specific** (`vercel.json`, `fly.toml`) — invariants the LLM doesn't reliably reproduce.
- **Configuration with strict schemas** (Grafana dashboard JSON, Promptfoo eval cases) — easier to ship golden vs. regenerate.
- **Multi-file scaffolds** (the Next.js chat template) — saves dozens of LLM-emit decisions.

A capability with `emit_files: []` ships no template tree — that's deliberate (see `eval.promptfoo`'s pattern, or the planned `eval.deepeval` / `eval.ragas` stubs).
