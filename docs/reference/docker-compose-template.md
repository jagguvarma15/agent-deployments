# Reference: Docker Compose Templates

Shared infrastructure and per-agent compose files. The base file provides Postgres, Redis, Qdrant, and Langfuse. Each agent extends it with its own app service.

## Key design decisions

- **Shared base** — all infrastructure defined once, extended per agent via `extends:`
- **Health checks on everything** — agents only start after dependencies are healthy
- **Volume persistence** — named volumes for all data stores
- **Env var defaults** — all configurable via environment, with sensible defaults for local dev
- **Langfuse stack** — includes ClickHouse and MinIO as Langfuse v2 dependencies

---

## Base compose (shared infrastructure)

```yaml
# Base docker-compose for agent projects
#
# Each agent extends this file and adds its app service.
# Usage in agent's docker-compose.yml:
#
#   services:
#     postgres:
#       extends:
#         file: ../path/to/docker-compose.base.yml
#         service: postgres
#     app:
#       build: .
#       depends_on:
#         postgres:
#           condition: service_healthy

services:
  # ---------------------------------------------------------------------------
  # Postgres 16
  # ---------------------------------------------------------------------------
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-agent}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-agent}
      POSTGRES_DB: ${POSTGRES_DB:-agent_db}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-agent}"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ---------------------------------------------------------------------------
  # Redis 7
  # ---------------------------------------------------------------------------
  redis:
    image: redis:7-alpine
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ---------------------------------------------------------------------------
  # Qdrant (vector DB)
  # ---------------------------------------------------------------------------
  qdrant:
    image: qdrant/qdrant:v1.12.0
    ports:
      - "${QDRANT_HTTP_PORT:-6333}:6333"
      - "${QDRANT_GRPC_PORT:-6334}:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:6333/healthz || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  # ---------------------------------------------------------------------------
  # Langfuse (observability / tracing)
  # ---------------------------------------------------------------------------
  langfuse-clickhouse:
    image: clickhouse/clickhouse-server:24
    environment:
      CLICKHOUSE_DB: langfuse
      CLICKHOUSE_USER: langfuse
      CLICKHOUSE_PASSWORD: langfuse
    volumes:
      - langfuse_clickhouse_data:/var/lib/clickhouse
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:8123/ping || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse-minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: langfuse
      MINIO_ROOT_PASSWORD: langfuse123
    volumes:
      - langfuse_minio_data:/data
    healthcheck:
      test: ["CMD-SHELL", "mc ready local || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5

  langfuse:
    image: langfuse/langfuse:2
    ports:
      - "${LANGFUSE_PORT:-3000}:3000"
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-agent}:${POSTGRES_PASSWORD:-agent}@postgres:5432/${LANGFUSE_DB:-langfuse}
      CLICKHOUSE_URL: http://langfuse-clickhouse:8123
      CLICKHOUSE_USER: langfuse
      CLICKHOUSE_PASSWORD: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT: http://langfuse-minio:9000
      LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY: langfuse123
      LANGFUSE_S3_EVENT_UPLOAD_BUCKET: langfuse
      LANGFUSE_S3_EVENT_UPLOAD_REGION: us-east-1
      LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE: "true"
      NEXTAUTH_SECRET: ${LANGFUSE_SECRET:-mysecret}
      NEXTAUTH_URL: http://localhost:${LANGFUSE_PORT:-3000}
      LANGFUSE_INIT_ORG_ID: agent-deployments
      LANGFUSE_INIT_ORG_NAME: agent-deployments
      LANGFUSE_INIT_PROJECT_ID: default
      LANGFUSE_INIT_PROJECT_NAME: default
      LANGFUSE_INIT_PROJECT_PUBLIC_KEY: ${LANGFUSE_PUBLIC_KEY:-pk-lf-local}
      LANGFUSE_INIT_PROJECT_SECRET_KEY: ${LANGFUSE_SECRET_KEY:-sk-lf-local}
      LANGFUSE_INIT_USER_EMAIL: admin@local.dev
      LANGFUSE_INIT_USER_PASSWORD: admin
      LANGFUSE_INIT_USER_NAME: Admin
      SALT: ${LANGFUSE_SALT:-salt}
    depends_on:
      postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-minio:
        condition: service_started
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3000/api/public/health || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  langfuse_clickhouse_data:
  langfuse_minio_data:
```

---

## Per-agent compose (example)

Each agent creates its own `docker-compose.yml` that extends the base services and adds its app:

```yaml
services:
  postgres:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: postgres

  redis:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: redis

  qdrant:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: qdrant

  langfuse-clickhouse:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: langfuse-clickhouse

  langfuse-minio:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: langfuse-minio

  langfuse:
    extends:
      file: ../path/to/docker-compose.base.yml
      service: langfuse
    depends_on:
      postgres:
        condition: service_healthy
      langfuse-clickhouse:
        condition: service_healthy
      langfuse-minio:
        condition: service_started

  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_healthy
    volumes:
      - ./app:/app/app  # hot-reload in development

volumes:
  postgres_data:
  redis_data:
  qdrant_data:
  langfuse_clickhouse_data:
  langfuse_minio_data:
```

## Adapting for your project

- **Not using Qdrant?** Remove the `qdrant` service (only needed for RAG agents)
- **Not using Langfuse?** Remove `langfuse`, `langfuse-clickhouse`, and `langfuse-minio`
- **Production?** Remove `volumes` mounts for hot-reload, add resource limits, use external managed databases
- **Standalone compose?** Inline the base services directly instead of using `extends:`
