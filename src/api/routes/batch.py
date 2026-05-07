from __future__ import annotations

import io
import re
import uuid
from pathlib import Path

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.settings import settings
from src.repositories import generation as generation_repo
from src.schemas.content import TextContent
from src.schemas.generation import AspectRatio, GenerationRequest, Resolution, TaskDB

router = APIRouter(prefix="/generations", tags=["generations"])

_FILENAME_RE = re.compile(r"^([^_]+)_([^_]+)_(\d+)\.xlsx$", re.IGNORECASE)


def _parse_output_dir(filename: str) -> str:
    """
    'seedance_entire_001.xlsx' → 'output/seedance/entire/001'
    Falls back to 'output/batch/<stem>' if pattern doesn't match.
    """
    m = _FILENAME_RE.match(filename)
    if m:
        project, series, number = m.group(1), m.group(2), m.group(3)
        return f"output/{project}/{series}/{number}"
    stem = Path(filename).stem
    return f"output/batch/{stem}"


async def _get_admin_user_id(db: AsyncSession) -> uuid.UUID:
    from src.repositories import user as user_repo
    from src.core.settings import settings
    user = await user_repo.get_by_username(db, settings.admin_username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Admin user not initialized")
    return user.id


@router.post(
    "/batch",
    response_model=list[TaskDB],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a batch of video generation tasks from an xlsx file",
)
async def create_batch(
    file: UploadFile = File(..., description="xlsx file with columns: number, prompt"),
    ratio: AspectRatio = Form(default=AspectRatio.ratio_16_9),
    resolution: Resolution = Form(default=Resolution.p720),
    duration: int = Form(default=8, ge=4, le=15),
    generate_audio: bool = Form(default=True),
    db: AsyncSession = Depends(get_db),
) -> list[TaskDB]:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    output_dir = _parse_output_dir(file.filename)
    logger.info("Batch upload | file={f} output_dir={d}", f=file.filename, d=output_dir)

    content = await file.read()
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse xlsx: {exc}") from exc

    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    rows = [(str(r[0]).strip(), str(r[1]).strip()) for r in rows if r[0] and r[1]]

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows found in xlsx")

    logger.info("Batch: {n} rows to process", n=len(rows))

    user_id = await _get_admin_user_id(db)
    created_tasks: list[TaskDB] = []

    for name, prompt in rows:
        local_path = f"{output_dir}/{name}.mp4"
        request = GenerationRequest(
            content=[TextContent(type="text", text=prompt)],
            ratio=ratio,
            resolution=resolution,
            duration=duration,
            generate_audio=generate_audio,
        )
        task = await generation_repo.create(
            db, user_id=user_id, request=request, name=name, local_path=local_path,
        )
        logger.debug("Batch: queued | name={name} id={id}", name=name, id=task.id)
        created_tasks.append(TaskDB.model_validate(task))

    logger.info("Batch: {n} tasks queued, worker will submit up to {limit} concurrently", n=len(created_tasks), limit=settings.seedance_max_concurrent)
    return created_tasks


@router.post("/batch/pause", summary="Pause a batch (stop submitting new tasks)")
async def pause_batch(output_dir: str, db: AsyncSession = Depends(get_db)) -> dict:
    count = await generation_repo.set_batch_status(db, output_dir, from_statuses=["queued"], to_status="paused")
    logger.info("Batch paused | dir={d} tasks={n}", d=output_dir, n=count)
    return {"paused": count, "output_dir": output_dir}


@router.post("/batch/resume", summary="Resume a paused batch")
async def resume_batch(output_dir: str, db: AsyncSession = Depends(get_db)) -> dict:
    count = await generation_repo.set_batch_status(db, output_dir, from_statuses=["paused"], to_status="queued")
    logger.info("Batch resumed | dir={d} tasks={n}", d=output_dir, n=count)
    return {"resumed": count, "output_dir": output_dir}


@router.post("/batch/cancel", summary="Cancel a batch (mark remaining queued/paused tasks as failed)")
async def cancel_batch(output_dir: str, db: AsyncSession = Depends(get_db)) -> dict:
    count = await generation_repo.set_batch_status(db, output_dir, from_statuses=["queued", "paused"], to_status="failed")
    logger.info("Batch cancelled | dir={d} tasks={n}", d=output_dir, n=count)
    return {"cancelled": count, "output_dir": output_dir}
