# Prototype Dockerfile — built from the repo root so that the shared
# common/python path dependency is available in the build context.
#
# Build:  docker build -f prototypes/parallel-enricher/python/Dockerfile -t agent-deployments/parallel-enricher-python .
# Or:     make docker-build PROTOTYPE=parallel-enricher TRACK=python

ARG PYTHON_VERSION=3.12
ARG UV_VERSION=0.5.10
ARG APP_DIR=prototypes/parallel-enricher/python

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# --- Build stage ---
FROM python:${PYTHON_VERSION}-slim AS builder
ARG APP_DIR

COPY --from=uv /uv /usr/local/bin/uv

# Place the app 3 levels deep so the path dependency ../../../common/python
# in uv.lock resolves to /repo/common/python.
WORKDIR /repo/proto/type/app

COPY common/python /repo/common/python
COPY ${APP_DIR}/pyproject.toml ${APP_DIR}/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ${APP_DIR}/ .
RUN uv sync --frozen --no-dev

# --- Runtime stage ---
FROM python:${PYTHON_VERSION}-slim AS runtime

RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --create-home app

WORKDIR /app

COPY --from=builder /repo/proto/type/app/.venv /app/.venv
COPY --from=builder /repo/proto/type/app .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
