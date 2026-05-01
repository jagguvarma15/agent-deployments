# Reference Templates

Reusable project scaffolding extracted from the original prototypes. Each file answers: **"How do I set up the build/deploy infrastructure?"**

| Template | What it provides |
|----------|-----------------|
| [Makefile](makefile-template.md) | Build, test, eval, lint, and Docker targets |
| [CI Pipeline](ci-template.md) | GitHub Actions workflow with change detection, three-tier testing |
| [Dockerfiles](docker-templates.md) | Multi-stage Python and TypeScript Dockerfiles |
| [Docker Compose](docker-compose-template.md) | Shared infrastructure (Postgres, Redis, Qdrant, Langfuse) + per-agent compose |

## How to use

These templates are starting points. Copy the relevant sections into your agent project and adapt paths, service names, and configuration to match your setup.
