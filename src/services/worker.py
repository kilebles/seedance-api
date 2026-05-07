from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from loguru import logger

from src.core.database import AsyncSessionLocal
from src.core.settings import settings
from src.repositories import generation as generation_repo
from src.services import seedance_client


async def _download_video(url: str, local_path: str) -> None:
    try:
        path = Path(local_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                with path.open("wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
        logger.success("Worker: video saved | path={p}", p=local_path)
    except Exception as exc:
        logger.error("Worker: failed to download video | path={p} exc={exc}", p=local_path, exc=exc)


async def _submit_queued() -> None:
    """Pick up queued tasks and submit to BytePlus up to the concurrency limit."""
    async with AsyncSessionLocal() as db:
        running = await generation_repo.count_running(db)
        slots = settings.seedance_max_concurrent - running
        if slots <= 0:
            return
        queued = await generation_repo.list_queued(db, limit=slots)

    if not queued:
        return

    logger.debug("Worker: submitting {n} queued task(s) ({slots} slots free)", n=len(queued), slots=slots)

    from datetime import datetime, timezone

    for task in queued:
        # Rebuild GenerationRequest from stored data to submit
        from src.schemas.generation import AspectRatio, GenerationRequest, Resolution
        from src.schemas.content import TextContent

        # Extract text prompt from stored content_items
        text_items = [i["text"] for i in (task.content_items or []) if i.get("type") == "text"]
        prompt = text_items[0] if text_items else ""

        request = GenerationRequest(
            content=[TextContent(type="text", text=prompt)],
            ratio=AspectRatio(task.ratio_requested),
            resolution=Resolution(task.resolution_requested),
            duration=task.duration_requested,
            generate_audio=task.generate_audio,
            watermark=task.watermark,
            seed=task.seed_requested,
        )

        try:
            byteplus_task = await seedance_client.submit_generation(request)
        except Exception as exc:
            logger.error("Worker: failed to submit task {id} — {exc}", id=task.id, exc=exc)
            async with AsyncSessionLocal() as db:
                await generation_repo.update(db, task.id, status="failed", error_message=str(exc))
            continue

        async with AsyncSessionLocal() as db:
            await generation_repo.update(
                db, task.id,
                external_id=byteplus_task.id,
                status="running",
                submitted_at=datetime.now(timezone.utc),
            )
        logger.info("Worker: submitted task {name} → {ext}", name=task.name or task.id, ext=byteplus_task.id)


async def _poll_running() -> None:
    """Poll BytePlus for status of all running tasks."""
    async with AsyncSessionLocal() as db:
        pending = await generation_repo.list_pending(db)

    if not pending:
        return

    logger.debug("Worker: polling {n} running task(s)", n=len(pending))

    for task in pending:
        try:
            result = await seedance_client.get_task(task.external_id)
        except Exception as exc:
            logger.error("Worker: failed to poll task {id} — {exc}", id=task.external_id, exc=exc)
            continue

        fields: dict = {"status": result.status.value}

        if result.status.value == "succeeded":
            video_url = result.content.video_url if result.content else None
            fields.update(
                video_url=video_url,
                last_frame_url=result.content.last_frame_image_url if result.content else None,
                duration_actual=result.duration,
                ratio_actual=result.ratio,
                resolution_actual=result.resolution,
                seed_actual=result.seed,
                framespersecond=result.framespersecond,
            )
            logger.success(
                "Worker: task {name} succeeded | duration={dur}s ratio={ratio}",
                name=task.name or task.external_id,
                dur=result.duration,
                ratio=result.ratio,
            )
            if video_url and task.local_path:
                await _download_video(video_url, task.local_path)

        elif result.status.value == "failed":
            error = result.error or {}
            fields.update(
                error_code=error.get("code"),
                error_message=error.get("message"),
            )
            logger.error(
                "Worker: task {name} failed | {code}: {msg}",
                name=task.name or task.external_id,
                code=fields["error_code"],
                msg=fields["error_message"],
            )

        async with AsyncSessionLocal() as db:
            await generation_repo.update(db, task.id, **fields)


async def poll_loop() -> None:
    logger.info(
        "Worker started | interval={interval}s max_concurrent={limit}",
        interval=settings.worker_poll_interval,
        limit=settings.seedance_max_concurrent,
    )
    while True:
        try:
            await _submit_queued()
            await _poll_running()
        except Exception as exc:
            logger.error("Worker: unexpected error — {exc}", exc=exc)
        await asyncio.sleep(settings.worker_poll_interval)
