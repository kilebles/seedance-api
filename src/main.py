from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from src.api.routes.generations import router as generations_router
from src.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="Seedance Video Generation API",
    description="Proxy API for BytePlus Seedance 2.0 video generation.",
    version="0.1.0",
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
