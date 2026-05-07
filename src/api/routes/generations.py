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

    user_id = await _get_admin_user_id(db)
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
