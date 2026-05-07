from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException, Path, Request, status
from loguru import logger

from src.schemas.generation import GenerationRequest, GenerationTaskResponse, TaskResultResponse
from src.services.seedance_client import get_task, submit_generation

router = APIRouter(prefix="/generations", tags=["generations"])


@router.post(
    "/tasks",
    response_model=GenerationTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a video generation task",
)
async def create_task(request: Request, body: GenerationRequest) -> GenerationTaskResponse:
    logger.info(
        "POST /generations/tasks | model={model} content_items={n}",
        model=body.model,
        n=len(body.content),
    )
    try:
        result = await submit_generation(body)
        logger.info("Task accepted | task_id={task_id}", task_id=result.id)
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Upstream HTTP error | status={status} body={body}",
            status=exc.response.status_code,
            body=exc.response.text,
        )
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.RequestError as exc:
        logger.error("Upstream request error | {exc}", exc=exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResultResponse,
    summary="Get the status / result of a generation task",
)
async def read_task(
    task_id: str = Path(..., description="Task ID returned by the submit endpoint"),
) -> TaskResultResponse:
    logger.info("GET /generations/tasks/{task_id}", task_id=task_id)
    try:
        result = await get_task(task_id)
        logger.info(
            "Task polled | task_id={task_id} status={status}",
            task_id=task_id,
            status=result.status,
        )
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Upstream HTTP error | task_id={task_id} status={status} body={body}",
            task_id=task_id,
            status=exc.response.status_code,
            body=exc.response.text,
        )
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text) from exc
    except httpx.RequestError as exc:
        logger.error("Upstream request error | task_id={task_id} {exc}", task_id=task_id, exc=exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
