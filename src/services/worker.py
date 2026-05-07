from __future__ import annotations

import asyncio

from loguru import logger

from src.core.database import AsyncSessionLocal
from src.core.settings import settings
from src.repositories import generation as generation_repo
from src.services import seedance_client


async def _poll_once() -> None:
    async with AsyncSessionLocal() as db:
        pending = await generation_repo.list_pending(db)

    if not pending:
        return

    logger.debug("Worker: polling {n} pending task(s)", n=len(pending))

    for task in pending:
        try:
            result = await seedance_client.get_task(task.external_id)
        except Exception as exc:
            logger.error("Worker: failed to poll task {id} — {exc}", id=task.external_id, exc=exc)
            continue

        fields: dict = {"status": result.status.value}

        if result.status.value == "succeeded":
            fields.update(
                video_url=result.content.video_url if result.content else None,
                last_frame_url=result.content.last_frame_image_url if result.content else None,
                duration_actual=result.duration,
                ratio_actual=result.ratio,
                resolution_actual=result.resolution,
                seed_actual=result.seed,
                framespersecond=result.framespersecond,
            )
            logger.success(
                "Worker: task {ext} succeeded | duration={dur}s ratio={ratio} url={url}",
                ext=task.external_id,
                dur=result.duration,
                ratio=result.ratio,
                url=fields["video_url"],
            )

        elif result.status.value == "failed":
            error = result.error or {}
            fields.update(
                error_code=error.get("code"),
                error_message=error.get("message"),
            )
            logger.error(
                "Worker: task {ext} failed | {code}: {msg}",
                ext=task.external_id,
                code=fields["error_code"],
                msg=fields["error_message"],
            )

        async with AsyncSessionLocal() as db:
            await generation_repo.update(db, task.id, **fields)


async def poll_loop() -> None:
    logger.info("Worker started, interval={interval}s", interval=settings.worker_poll_interval)
    while True:
        try:
            await _poll_once()
        except Exception as exc:
            logger.error("Worker: unexpected error — {exc}", exc=exc)
        await asyncio.sleep(settings.worker_poll_interval)
