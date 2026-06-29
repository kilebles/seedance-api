from __future__ import annotations

import asyncio
import uuid

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal, get_db
from src.repositories import image as image_repo
from src.schemas.image import ImageGenerationRequest, ImageTaskDB

router = APIRouter(prefix="/images", tags=["images"])


async def _get_admin_user_id(db: AsyncSession) -> uuid.UUID:
    from src.repositories import user as user_repo
    from src.core.settings import settings
    user = await user_repo.get_by_username(db, settings.admin_username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin user not initialized")
    return user.id


async def _run_image_generation(task_id: uuid.UUID, request: ImageGenerationRequest) -> None:
    """Background task: call BytePlus, update DB with result."""
    from src.services import seedance_client
    try:
        result = await seedance_client.generate_image(request)
    except Exception as exc:
        logger.error("Image generation failed | id={id} error={e}", id=task_id, e=exc)
        async with AsyncSessionLocal() as db:
            error_msg = str(exc)
            if isinstance(exc, httpx.HTTPStatusError):
                try:
                    err = exc.response.json().get("error", {})
                    error_msg = err.get("message") or error_msg
                except Exception:
                    pass
            await image_repo.update(db, task_id, status="failed", error_message=error_msg)
        return

    top_error = result.get("error")
    if top_error:
        async with AsyncSessionLocal() as db:
            await image_repo.update(
                db, task_id,
                status="failed",
                error_code=str(top_error.get("code", "")),
                error_message=top_error.get("message", ""),
            )
        return

    data = result.get("data", [])
    usage = result.get("usage", {})
    first = data[0] if data else {}
    item_error = first.get("error")

    async with AsyncSessionLocal() as db:
        if item_error:
            await image_repo.update(
                db, task_id,
                status="failed",
                error_code=str(item_error.get("code", "")),
                error_message=item_error.get("message", ""),
                output_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
            )
        else:
            await image_repo.update(
                db, task_id,
                status="succeeded",
                image_url=first.get("url"),
                image_size=first.get("size"),
                output_tokens=usage.get("output_tokens"),
                total_tokens=usage.get("total_tokens"),
            )
            logger.success("Image generated | id={id} url={url}", id=task_id, url=first.get("url"))


@router.post(
    "/tasks",
    response_model=ImageTaskDB,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Generate an image with Seedream-5-0",
)
async def create_image_task(
    body: ImageGenerationRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ImageTaskDB:
    logger.info("POST /images/tasks | model={model}", model=body.model)

    user_id = await _get_admin_user_id(db)

    # Save immediately with status "running"
    task = await image_repo.create(db, user_id=user_id, request=body, status="running")

    # Run generation in background
    background_tasks.add_task(_run_image_generation, task.id, body)

    return ImageTaskDB.model_validate(task)


@router.get(
    "/tasks/{task_id}",
    response_model=ImageTaskDB,
    summary="Get an image generation task",
)
async def read_image_task(
    task_id: uuid.UUID = Path(...),
    db: AsyncSession = Depends(get_db),
) -> ImageTaskDB:
    task = await image_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return ImageTaskDB.model_validate(task)


@router.get(
    "/tasks",
    response_model=list[ImageTaskDB],
    summary="List all image generation tasks",
)
async def list_image_tasks(db: AsyncSession = Depends(get_db)) -> list[ImageTaskDB]:
    from sqlalchemy import select
    from src.models.image import ImageTask
    result = await db.execute(select(ImageTask).order_by(ImageTask.created_at.desc()))
    return [ImageTaskDB.model_validate(t) for t in result.scalars().all()]
