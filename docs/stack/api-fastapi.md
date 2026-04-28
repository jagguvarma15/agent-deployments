# Stack pick: FastAPI

**Choice:** FastAPI 0.115 + Uvicorn 0.32 (behind Gunicorn for prod)
**Used for:** Python API layer for all agent prototypes

## Why this over alternatives

| Option | Why not |
|--------|---------|
| Flask | No async support, no auto-generated OpenAPI docs |
| Django REST | Too heavy for agent-serving; ORM is unnecessary when using SQLAlchemy directly |
| Litestar | Strong alternative but smaller ecosystem; FastAPI has more community tooling for AI/ML |
| Starlette | FastAPI is built on Starlette and adds validation, docs, and dependency injection |

## Local setup

FastAPI runs inside the `app` service in each prototype's `docker-compose.yml`:

```yaml
app:
  build:
    context: ../../..
    dockerfile: prototypes/<name>/python/Dockerfile
  ports:
    - "8000:8000"
  env_file: .env
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
```

For local dev without Docker:

```bash
cd prototypes/<name>/python
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

## Config knobs that matter

| Knob | Default | Effect |
|------|---------|--------|
| `--reload` | off | Auto-reload on file changes (dev only) |
| `--workers` | 1 | Number of Uvicorn workers. Use Gunicorn with `uvicorn.workers.UvicornWorker` for prod |
| `--host` | `127.0.0.1` | Bind address. Set to `0.0.0.0` in Docker |
| Port | 8000 | All prototypes use 8000 |

## Integration pattern

### App entrypoint (`app/main.py`)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from agent_common.logs import configure

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure("my-agent", env=settings.app_env, log_level=settings.log_level)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()

app = FastAPI(title="my-agent", lifespan=lifespan)
app.include_router(query_router)

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Route handler pattern

```python
@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id)
    log.info("processing_query")
    answer, citations = await answer_question(request.question)
    return QueryResponse(answer=answer, citations=citations, trace_id=trace_id)
```

### Adding cross-cutting concerns

```python
from agent_common.auth import get_current_user
from agent_common.ratelimit import build_limiter

# Auth
user_dep = get_current_user(settings.jwt_secret)

# Rate limiting
limiter = build_limiter(settings.redis_url)
app.state.limiter = limiter
```

## Where used in repo

Every Python prototype uses FastAPI as its API layer: `prototypes/<name>/python/app/main.py`.

## Swapping to Litestar

1. Replace `FastAPI` with `Litestar`, `APIRouter` with Litestar controllers.
2. Replace `Depends()` with Litestar's dependency injection.
3. Replace `pydantic` models with Litestar's `DTOData` or keep Pydantic (Litestar supports both).
4. Lifespan hooks work similarly.

This is a **multi-file swap** (main.py + all route files + auth dependency).
