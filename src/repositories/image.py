from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.image import ImageTask
from src.schemas.image import ImageGenerationRequest


async def create(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: ImageGenerationRequest,
    image_url: str | None = None,
    image_size: str | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
    status: str = "succeeded",
    error_code: str | None = None,
    error_message: str | None = None,
) -> ImageTask:
    task = ImageTask(
        user_id=user_id,
        model=request.model,
        prompt=request.prompt,
        size_requested=request.size,
        watermark=request.watermark,
        seed_requested=request.seed,
        status=status,
        image_url=image_url,
        image_size=image_size,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        error_code=error_code,
        error_message=error_message,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get(db: AsyncSession, task_id: uuid.UUID) -> ImageTask | None:
    result = await db.execute(select(ImageTask).where(ImageTask.id == task_id))
    return result.scalar_one_or_none()
