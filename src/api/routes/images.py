from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
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


@router.post(
    "/tasks",
    response_model=ImageTaskDB,
    status_code=status.HTTP_201_CREATED,
    summary="Generate an image with Seedream-5-0-lite",
)
async def create_image_task(
    body: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> ImageTaskDB:
    from src.services import seedance_client

    logger.info("POST /images/tasks | model={model}", model=body.model)

    user_id = await _get_admin_user_id(db)

    try:
        result = await seedance_client.generate_image(body)
    except httpx.HTTPStatusError as exc:
        try:
            err = exc.response.json().get("error", {})
            msg = err.get("message") or str(exc)
        except Exception:
            msg = str(exc)
        raise HTTPException(status_code=exc.response.status_code, detail=msg)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    top_error = result.get("error")
    if top_error:
        task = await image_repo.create(
            db,
            user_id=user_id,
            request=body,
            status="failed",
            error_code=str(top_error.get("code", "")),
            error_message=top_error.get("message", ""),
        )
        return ImageTaskDB.model_validate(task)

    data = result.get("data", [])
    usage = result.get("usage", {})
    output_tokens = usage.get("output_tokens")
    total_tokens = usage.get("total_tokens")

    first = data[0] if data else {}
    item_error = first.get("error")

    if item_error:
        task = await image_repo.create(
            db,
            user_id=user_id,
            request=body,
            status="failed",
            error_code=str(item_error.get("code", "")),
            error_message=item_error.get("message", ""),
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    else:
        task = await image_repo.create(
            db,
            user_id=user_id,
            request=body,
            status="succeeded",
            image_url=first.get("url"),
            image_size=first.get("size"),
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

    logger.success(
        "Image generated | id={id} status={status} url={url}",
        id=task.id,
        status=task.status,
        url=task.image_url,
    )
    return ImageTaskDB.model_validate(task)


@router.get(
    "/tasks/{task_id}",
    response_model=ImageTaskDB,
    summary="Get an image generation task",
)
async def read_image_task(
    task_id: uuid.UUID = Path(..., description="Image task UUID"),
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
    tasks = result.scalars().all()
    return [ImageTaskDB.model_validate(t) for t in tasks]
