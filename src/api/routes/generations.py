from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.repositories import generation as generation_repo
from src.schemas.generation import GenerationRequest, TaskDB

router = APIRouter(prefix="/generations", tags=["generations"])


@router.get("/proxy", include_in_schema=False)
async def proxy_video(url: str = Query(...)):
    """Proxy a BytePlus video URL so the browser can read it cross-origin for canvas thumbnail."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    content_type = resp.headers.get("content-type", "video/mp4")

    async def stream():
        yield resp.content

    return StreamingResponse(
        stream(),
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=3600"},
    )


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
        try:
            byteplus_task = await seedance_client.submit_generation(body)
        except Exception as exc:
            import httpx as _httpx
            if isinstance(exc, _httpx.HTTPStatusError):
                try:
                    err = exc.response.json().get("error", {})
                    msg = err.get("message") or str(exc)
                except Exception:
                    msg = str(exc)
                raise HTTPException(status_code=exc.response.status_code, detail=msg)
            raise HTTPException(status_code=502, detail=str(exc))
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
async def list_tasks(
    batch_id: str | None = Query(default=None, description="Filter by batch_id"),
    db: AsyncSession = Depends(get_db),
) -> list[TaskDB]:
    from sqlalchemy import select
    from src.models.generation import GenerationTask
    q = select(GenerationTask)
    if batch_id:
        q = q.where(GenerationTask.batch_id == batch_id)
    q = q.order_by(GenerationTask.created_at.desc())
    result = await db.execute(q)
    tasks = result.scalars().all()
    return [TaskDB.model_validate(t) for t in tasks]


@router.post(
    "/batches/{batch_id}/retry-failed",
    summary="Re-queue failed tasks in a batch",
)
async def retry_batch_failed(
    batch_id: str = Path(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = await generation_repo.set_batch_status_by_id(db, batch_id, from_statuses=["failed"], to_status="queued")
    logger.info("Batch retry-failed | batch={bid} count={n}", bid=batch_id[:8], n=count)
    return {"retried": count}


@router.get(
    "/batches",
    summary="List all batches (grouped by batch_id)",
)
async def list_batches(db: AsyncSession = Depends(get_db)) -> list[dict]:
    from sqlalchemy import select, func as sqlfunc, case
    from src.models.generation import GenerationTask
    TERMINAL = ("succeeded", "failed", "expired", "cancelled")
    done_case = case(
        *[(GenerationTask.status.in_(TERMINAL), 1)],
        else_=0,
    )
    failed_case = case(
        *[(GenerationTask.status == "failed", 1)],
        else_=0,
    )
    q = (
        select(
            GenerationTask.batch_id,
            sqlfunc.min(GenerationTask.local_path).label("local_path"),
            sqlfunc.count().label("total"),
            sqlfunc.sum(done_case).label("done"),
            sqlfunc.sum(failed_case).label("failed"),
            sqlfunc.min(GenerationTask.created_at).label("created_at"),
            sqlfunc.min(GenerationTask.model).label("model"),
            sqlfunc.min(GenerationTask.resolution_requested).label("resolution"),
            sqlfunc.min(GenerationTask.upscale_resolution).label("upscale_resolution"),
        )
        .where(GenerationTask.batch_id.isnot(None))
        .group_by(GenerationTask.batch_id)
        .order_by(sqlfunc.min(GenerationTask.created_at).desc())
    )
    result = await db.execute(q)
    rows = result.mappings().all()
    out = []
    for r in rows:
        # derive display name from local_path: "output/batch/SeeDance_xxx_720p/1.mp4" → "SeeDance_xxx_720p"
        lp = r["local_path"] or ""
        parts = lp.replace("\\", "/").split("/")
        dir_name = parts[2] if len(parts) >= 3 else r["batch_id"]
        out.append({
            "batch_id": r["batch_id"],
            "name": dir_name,
            "total": r["total"],
            "done": int(r["done"] or 0),
            "failed": int(r["failed"] or 0),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "model": r["model"],
            "resolution": r["resolution"],
            "upscale_resolution": r["upscale_resolution"],
        })
    return out


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


@router.get("/enhance/stats", summary="Topaz enhance billing stats")
async def enhance_stats(db: AsyncSession = Depends(get_db)) -> dict:
    from sqlalchemy import select, func as sqlfunc
    from src.models.enhance import EnhanceTask
    result = await db.execute(
        select(
            EnhanceTask.output_resolution,
            sqlfunc.count().label("total"),
            sqlfunc.sum(EnhanceTask.cost_credits).label("total_credits"),
        )
        .where(EnhanceTask.status == "complete")
        .group_by(EnhanceTask.output_resolution)
    )
    rows = result.mappings().all()
    return {
        "by_resolution": [
            {
                "resolution": r["output_resolution"],
                "count": r["total"],
                "total_credits": int(r["total_credits"] or 0),
            }
            for r in rows
        ],
        "total_count": sum(r["total"] for r in rows),
        "total_credits": sum(int(r["total_credits"] or 0) for r in rows),
    }
