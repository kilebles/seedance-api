from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enhance import EnhanceTask


async def create(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    source_url: str,
    source_width: int,
    source_height: int,
    source_fps: float,
    source_duration: float,
    source_frame_count: int,
    source_size: int,
    source_container: str = "mp4",
    output_resolution: str = "4k",
    generation_task_id: uuid.UUID | None = None,
    local_path: str | None = None,
) -> EnhanceTask:
    task = EnhanceTask(
        user_id=user_id,
        source_url=source_url,
        source_width=source_width,
        source_height=source_height,
        source_fps=source_fps,
        source_duration=source_duration,
        source_frame_count=source_frame_count,
        source_size=source_size,
        source_container=source_container,
        output_resolution=output_resolution,
        generation_task_id=generation_task_id,
        local_path=local_path,
        status="queued",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def update(db: AsyncSession, task_id: uuid.UUID, **fields) -> EnhanceTask:
    result = await db.execute(select(EnhanceTask).where(EnhanceTask.id == task_id))
    task = result.scalar_one()
    for key, value in fields.items():
        setattr(task, key, value)
    task.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(task)
    return task


async def get(db: AsyncSession, task_id: uuid.UUID) -> EnhanceTask | None:
    result = await db.execute(select(EnhanceTask).where(EnhanceTask.id == task_id))
    return result.scalar_one_or_none()


async def list_processing(db: AsyncSession) -> list[EnhanceTask]:
    """Tasks submitted to Topaz that need status polling (have request_id, not terminal)."""
    result = await db.execute(
        select(EnhanceTask)
        .where(EnhanceTask.request_id.is_not(None))
        .where(EnhanceTask.status.not_in(["complete", "failed", "canceled"]))
    )
    return list(result.scalars().all())


async def list_queued(db: AsyncSession) -> list[EnhanceTask]:
    """Tasks waiting to be submitted to Topaz (status=queued, no request_id yet)."""
    result = await db.execute(
        select(EnhanceTask)
        .where(EnhanceTask.status == "queued")
        .order_by(EnhanceTask.created_at.asc())
    )
    return list(result.scalars().all())
