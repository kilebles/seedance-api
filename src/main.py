from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
import bcrypt

from src.api.routes.generations import router as generations_router
from src.core.database import AsyncSessionLocal, engine
from src.core.logging import setup_logging
from src.core.settings import settings
from src.repositories import user as user_repo
from src.services.worker import poll_loop

setup_logging()

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Running migrations...")
    await asyncio.to_thread(_run_migrations)
    logger.info("Migrations done")

    try:
        async with AsyncSessionLocal() as db:
            user = await user_repo.get_by_username(db, settings.admin_username)
            if user is None:
                await user_repo.create(db, settings.admin_username, _hash_password(settings.admin_password))
                logger.info("Admin user created | username={u}", u=settings.admin_username)
            else:
                logger.info("Admin user found | username={u}", u=settings.admin_username)
    except Exception:
        logger.exception("Failed during startup")
        raise

    worker_task = asyncio.create_task(poll_loop())

    yield

    # Shutdown
    worker_task.cancel()
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Seedance Video Generation API",
    description="Proxy API for BytePlus Seedance 2.0 video generation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(generations_router)

_NOISY_PATHS = {"/docs", "/openapi.json", "/redoc", "/health"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    path = request.url.path
    response = await call_next(request)

    if path not in _NOISY_PATHS and path.startswith("/generations"):
        logger.info(
            "{method} {path} | client={client} status={status}",
            method=request.method,
            path=path,
            client=request.client.host if request.client else "unknown",
            status=response.status_code,
        )

    return response


@app.get("/health", include_in_schema=False)
async def health() -> JSONResponse:
    logger.debug("Health check")
    return JSONResponse({"status": "ok"})
