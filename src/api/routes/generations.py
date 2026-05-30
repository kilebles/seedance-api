from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories import generation as generation_repo
from src.schemas.generation import GenerationRequest, TaskDB

router = APIRouter(prefix="/generations", tags=["generations"])


async def _get_admin_user_id(db: AsyncSession) -> uuid.UUID:
    """Return the fixed admin user's ID. Created on startup, always exists."""
    from src.repositories import user as user_repo
    from src.core.settings import settings
    user = await user_repo.get_by_username(db, settings.admin_username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin user not initialized")
    return user.id


@router.post(
    "/tasks",
    response_model=TaskDB,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a video generation task",
)
async def create_task(
    request: Request,
    body: GenerationRequest,
    db: AsyncSession = Depends(get_db),
) -> TaskDB:
    logger.info(
        "POST /generations/tasks | model={model} content_items={n}",
        model=body.model,
        n=len(body.content),
    )

    from datetime import datetime, timezone
    from src.services import seedance_client

    user_id = await _get_admin_user_id(db)

    # If any content item contains base64, submit to BytePlus immediately —
    # base64 is stripped before saving to DB so it can't be replayed by the worker.
    has_base64 = any(
        getattr(getattr(item, key, None), "url", "").startswith("data:")
        for item in body.content
        for key in ("image_url", "video_url", "audio_url")
    )

    if has_base64:
        byteplus_task = await seedance_client.submit_generation(body)
        task = await generation_repo.create(
            db, user_id=user_id, request=body,
            external_id=byteplus_task.id,
            status="running",
            submitted_at=datetime.now(timezone.utc),
        )
        logger.info("Task submitted immediately | id={id} ext={ext}", id=task.id, ext=byteplus_task.id)
    else:
        task = await generation_repo.create(db, user_id=user_id, request=body)
        logger.info("Task queued | id={id}", id=task.id)

    return TaskDB.model_validate(task)


@router.get(
    "/tasks/{task_id}",
    response_model=TaskDB,
    summary="Get the status / result of a generation task",
)
async def read_task(
    task_id: uuid.UUID = Path(..., description="Task UUID from our DB"),
    db: AsyncSession = Depends(get_db),
) -> TaskDB:
    logger.info("GET /generations/tasks/{task_id}", task_id=task_id)

    task = await generation_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return TaskDB.model_validate(task)


@router.get(
    "/tasks",
    response_model=list[TaskDB],
    summary="List all generation tasks",
)
async def list_tasks(db: AsyncSession = Depends(get_db)) -> list[TaskDB]:
    from sqlalchemy import select
    from src.models.generation import GenerationTask
    result = await db.execute(select(GenerationTask).order_by(GenerationTask.created_at.desc()))
    tasks = result.scalars().all()
    return [TaskDB.model_validate(t) for t in tasks]


@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel a queued or paused task",
)
async def cancel_task(
    task_id: uuid.UUID = Path(..., description="Task UUID"),
    db: AsyncSession = Depends(get_db),
) -> None:
    task = await generation_repo.get(db, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status not in ("queued", "paused"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel task with status '{task.status}'. Only queued/paused tasks can be cancelled.",
        )
    await generation_repo.update(db, task_id, status="cancelled")
    logger.info("Task cancelled | id={id}", id=task_id)


@router.post(
    "/tasks/cancel-bulk",
    summary="Cancel multiple queued or paused tasks",
)
async def cancel_tasks_bulk(
    body: dict,
    db: AsyncSession = Depends(get_db),
) -> dict:
    task_ids: list[str] = body.get("task_ids", [])
    if not task_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="task_ids is required")

    cancelled = 0
    skipped = 0
    for tid_str in task_ids:
        try:
            tid = uuid.UUID(tid_str)
        except ValueError:
            skipped += 1
            continue
        task = await generation_repo.get(db, tid)
        if task is None or task.status not in ("queued", "paused"):
            skipped += 1
            continue
        await generation_repo.update(db, tid, status="cancelled")
        cancelled += 1

    logger.info("Bulk cancel | cancelled={c} skipped={s}", c=cancelled, s=skipped)
    return {"cancelled": cancelled, "skipped": skipped}
