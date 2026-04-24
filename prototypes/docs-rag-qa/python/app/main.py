"""FastAPI entrypoint for docs-rag-qa."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from app.api.documents import router as documents_router
from app.api.query import router as query_router
from app.db.models import Base
from app.db.session import engine
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent_common.logs import configure

    configure(settings.app_name, env=settings.app_env, log_level=settings.log_level)

    logger = structlog.get_logger()
    logger.info("starting", app=settings.app_name)

    # Create tables (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.include_router(documents_router)
app.include_router(query_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
