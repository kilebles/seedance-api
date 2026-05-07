from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.generation import GenerationTask
from src.schemas.generation import GenerationRequest


def _content_items_meta(request: GenerationRequest) -> list[dict]:
    """Strip base64 payloads, keep only type/role/url metadata."""
    items = []
    for item in request.content:
        d = item.model_dump(mode="json")
        # drop base64 values to avoid storing MBs in DB
        for media_key in ("image_url", "video_url", "audio_url"):
            if media_key in d and isinstance(d[media_key].get("url"), str):
                url = d[media_key]["url"]
                if url.startswith("data:"):
                    d[media_key]["url"] = "<base64>"
        items.append(d)
    return items


async def create(db: AsyncSession, user_id: uuid.UUID, request: GenerationRequest) -> GenerationTask:
    task = GenerationTask(
        user_id=user_id,
        model=request.model,
        ratio_requested=request.ratio.value,
        resolution_requested=request.resolution.value,
        duration_requested=request.duration,
        generate_audio=request.generate_audio,
        watermark=request.watermark,
        seed_requested=request.seed,
        content_items=_content_items_meta(request),
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update(db: AsyncSession, task_id: uuid.UUID, **fields) -> GenerationTask:
    result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
    task = result.scalar_one()
    for key, value in fields.items():
        setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


async def get(db: AsyncSession, task_id: uuid.UUID) -> GenerationTask | None:
    result = await db.execute(select(GenerationTask).where(GenerationTask.id == task_id))
    return result.scalar_one_or_none()


async def list_pending(db: AsyncSession) -> list[GenerationTask]:
    """Return all tasks that still need polling (have external_id and are not terminal)."""
    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.external_id.is_not(None))
        .where(GenerationTask.status.in_(["queued", "running"]))
    )
    return list(result.scalars().all())
