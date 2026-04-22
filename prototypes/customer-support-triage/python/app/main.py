"""FastAPI entrypoint for the prototype."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from agent_common.logs import configure

    configure(settings.app_name, env=settings.app_env, log_level=settings.log_level)
    yield
    # Shutdown


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok"}
