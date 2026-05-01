# Reference: Dockerfile Templates

Multi-stage Dockerfiles for Python (FastAPI + uv) and TypeScript (Hono + pnpm) agent projects.

## Key design decisions

- **Multi-stage builds** — separate builder and runtime stages for smaller production images
- **Non-root user** — security best practice, UID/GID 1001
- **Layer caching** — dependency files copied before source for optimal cache hits
- **Health checks** — built-in Docker HEALTHCHECK for orchestrator compatibility

---

## Python Dockerfile

Uses `uv` for fast dependency resolution. Produces a slim Python image with only production dependencies.

```dockerfile
# Multi-stage Python Dockerfile for agent projects
#
# Build args:
#   PYTHON_VERSION - Python version (default: 3.12)
#   UV_VERSION     - uv installer version (default: 0.5.10)

ARG PYTHON_VERSION=3.12

# ---------------------------------------------------------------------------
# Stage 1: Build — install dependencies
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS builder

ARG UV_VERSION=0.5.10

# Install uv
COPY --from=ghcr.io/astral-sh/uv:${UV_VERSION} /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev deps in production)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime

# Security: non-root user
RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --create-home app

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY --from=builder /app .

# Ensure the venv is on PATH
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Switch to non-root user
USER app

# Default port for FastAPI
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command — override per agent if needed
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## TypeScript Dockerfile

Uses `pnpm` for dependency management. Compiles TypeScript and prunes dev dependencies for a minimal runtime image.

```dockerfile
# Multi-stage TypeScript Dockerfile for agent projects
#
# Build args:
#   NODE_VERSION - Node.js version (default: 22)

ARG NODE_VERSION=22

# ---------------------------------------------------------------------------
# Stage 1: Build — install dependencies and compile
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS builder

# Install pnpm
RUN corepack enable && corepack prepare pnpm@9 --activate

WORKDIR /app

# Copy dependency files first for layer caching
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install --frozen-lockfile

# Copy source
COPY . .

# Build TypeScript
RUN pnpm run build

# Prune dev dependencies
RUN pnpm prune --prod

# ---------------------------------------------------------------------------
# Stage 2: Runtime — minimal image
# ---------------------------------------------------------------------------
FROM node:${NODE_VERSION}-alpine AS runtime

# Security: non-root user
RUN addgroup --gid 1001 app && \
    adduser --uid 1001 --ingroup app --disabled-password app

WORKDIR /app

# Copy built output and production deps from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

# Switch to non-root user
USER app

# Default port for Hono
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8000/health || exit 1

# Default command — override per agent if needed
CMD ["node", "dist/index.js"]
```

## Adapting for your project

- Adjust `CMD` to match your entry point (`app.main:app` for Python, `dist/index.js` for TS)
- Add build args for custom versions
- For monorepo setups, adjust `COPY` commands to include shared workspace packages
