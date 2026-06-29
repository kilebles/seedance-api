from __future__ import annotations

import httpx
from loguru import logger

from src.core.settings import settings
from src.schemas.generation import GenerationRequest, GenerationTaskResponse, TaskResultResponse
from src.schemas.image import ImageGenerationRequest

_TASKS_PATH = "/api/v3/contents/generations/tasks"
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.seedance_base_url,
        headers={
            "Authorization": f"Bearer {settings.seedance_api_key}",
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
    )


async def submit_generation(request: GenerationRequest) -> GenerationTaskResponse:
    payload = request.model_dump(mode="json", exclude_none=True)
    logger.info(
        "Submitting generation task | model={model} content_items={n} ratio={ratio} duration={duration} generate_audio={audio}",
        model=payload.get("model"),
        n=len(payload.get("content", [])),
        ratio=payload.get("ratio"),
        duration=payload.get("duration"),
        audio=payload.get("generate_audio"),
    )
    logger.debug("Request payload: {payload}", payload=payload)

    async with _make_client() as client:
        response = await client.post(_TASKS_PATH, json=payload)

    logger.debug(
        "BytePlus response | status={status} body={body}",
        status=response.status_code,
        body=response.text,
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "BytePlus API error | status={status} body={body}",
            status=response.status_code,
            body=response.text,
        )
        raise

    result = GenerationTaskResponse.model_validate(response.json())
    logger.success("Task submitted | task_id={task_id}", task_id=result.id)
    return result


async def get_task(task_id: str) -> TaskResultResponse:
    logger.debug("Polling task | task_id={task_id}", task_id=task_id)

    async with _make_client() as client:
        response = await client.get(f"{_TASKS_PATH}/{task_id}")

    logger.debug(
        "BytePlus response | task_id={task_id} status={status} body={body}",
        task_id=task_id,
        status=response.status_code,
        body=response.text,
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "BytePlus API error | task_id={task_id} status={status} body={body}",
            task_id=task_id,
            status=response.status_code,
            body=response.text,
        )
        raise

    result = TaskResultResponse.model_validate(response.json())

    if result.status == "succeeded":
        video_url = result.content.video_url if result.content else None
        logger.success(
            "Task succeeded | task_id={task_id} duration={duration}s ratio={ratio} video_url={url}",
            task_id=task_id,
            duration=result.duration,
            ratio=result.ratio,
            url=video_url,
        )
    elif result.status == "failed":
        logger.error(
            "Task failed | task_id={task_id} error={error}",
            task_id=task_id,
            error=result.error,
        )
    else:
        logger.info(
            "Task status | task_id={task_id} status={status}",
            task_id=task_id,
            status=result.status,
        )

    return result


_IMAGES_PATH = "/api/v3/images/generations"


async def generate_image(request: ImageGenerationRequest) -> dict:
    """Call BytePlus image generation API (synchronous, returns URL immediately)."""
    payload: dict = {
        "model": request.model,
        "prompt": request.prompt,
        "watermark": request.watermark,
    }
    if request.image is not None:
        payload["image"] = request.image
    if request.size is not None:
        payload["size"] = request.size
    if request.seed is not None:
        payload["seed"] = request.seed

    logger.info(
        "Submitting image generation | model={model} size={size}",
        model=payload["model"],
        size=payload.get("size"),
    )
    logger.debug("Image request payload: {payload}", payload={k: v for k, v in payload.items() if k != "image"})

    async with _make_client() as client:
        response = await client.post(_IMAGES_PATH, json=payload)

    logger.debug(
        "BytePlus image response | status={status} body={body}",
        status=response.status_code,
        body=response.text[:500],
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "BytePlus image API error | status={status} body={body}",
            status=response.status_code,
            body=response.text,
        )
        raise

    return response.json()
