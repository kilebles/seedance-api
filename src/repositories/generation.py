from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
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


async def create(
    db: AsyncSession,
    user_id: uuid.UUID,
    request: GenerationRequest,
    name: str | None = None,
    local_path: str | None = None,
) -> GenerationTask:
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
        name=name,
        local_path=local_path,
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
    """Tasks submitted to BytePlus that need status polling."""
    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.external_id.is_not(None))
        .where(GenerationTask.status.in_(["running"]))
    )
    return list(result.scalars().all())


async def count_running(db: AsyncSession) -> int:
    """Number of tasks currently submitted to BytePlus (running)."""
    result = await db.execute(
        select(func.count()).where(GenerationTask.status == "running")
    )
    return result.scalar_one()


async def list_queued(db: AsyncSession, limit: int) -> list[GenerationTask]:
    """Tasks waiting to be submitted to BytePlus, oldest first."""
    result = await db.execute(
        select(GenerationTask)
        .where(GenerationTask.status == "queued")
        .order_by(GenerationTask.created_at.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def set_batch_status(db: AsyncSession, output_dir: str, from_statuses: list[str], to_status: str) -> int:
    """Update status for all tasks in a batch (matched by local_path prefix). Returns count."""
    from sqlalchemy import update
    result = await db.execute(
        update(GenerationTask)
        .where(GenerationTask.local_path.like(f"{output_dir}/%"))
        .where(GenerationTask.status.in_(from_statuses))
        .values(status=to_status)
    )
    await db.commit()
    return result.rowcount
