from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
from loguru import logger

from src.core.database import AsyncSessionLocal
from src.core.settings import settings
from src.repositories import enhance as enhance_repo
from src.repositories import generation as generation_repo
from src.services import seedance_client, topaz_client


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
    from src.schemas.generation import AspectRatio, GenerationRequest, Resolution

    from pydantic import TypeAdapter
    from src.schemas.content import ContentItem
    content_adapter = TypeAdapter(list[ContentItem])

    for task in queued:
        request = GenerationRequest(
            model=task.model,
            content=content_adapter.validate_python(task.content_items or []),
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
            error_code, error_message = None, str(exc)
            if hasattr(exc, "response"):
                try:
                    body = exc.response.json()
                    err = body.get("error", {})
                    error_code = err.get("code")
                    error_message = err.get("message", str(exc))
                except Exception:
                    pass
            async with AsyncSessionLocal() as db:
                await generation_repo.update(db, task.id, status="failed", error_code=error_code, error_message=error_message)
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
            fps = result.framespersecond
            fields.update(
                video_url=video_url,
                last_frame_url=result.content.last_frame_image_url if result.content else None,
                duration_actual=result.duration,
                ratio_actual=result.ratio,
                resolution_actual=result.resolution,
                seed_actual=result.seed,
                framespersecond=fps,
                completion_tokens=result.usage.completion_tokens if result.usage else None,
                total_tokens=result.usage.total_tokens if result.usage else None,
            )
            logger.success(
                "Worker: task {name} succeeded | duration={dur}s ratio={ratio}",
                name=task.name or task.external_id,
                dur=result.duration,
                ratio=result.ratio,
            )
            if video_url and task.local_path:
                await _download_video(video_url, task.local_path)

            # Queue upscale if requested — pass result values directly (task ORM not yet updated)
            if video_url and task.upscale_resolution:
                await _queue_enhance_for_task(
                    task, video_url,
                    fps=result.framespersecond or 24,
                    duration=result.duration or 8,
                    resolution=result.resolution or task.resolution_requested,
                )

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


async def _queue_enhance_for_task(
    task, video_url: str,
    fps: int = 24,
    duration: int = 8,
    resolution: str | None = None,
    output_resolution: str | None = None,
) -> None:
    """Create an EnhanceTask for a just-succeeded GenerationTask."""
    frame_count = int(fps * duration)

    res_map = {"720p": (1280, 720), "480p": (854, 480)}
    res_str = resolution or task.resolution_requested or "720p"
    width, height = res_map.get(res_str, (1280, 720))

    out_res = output_resolution or task.upscale_resolution or "1080p"

    # Download video now to get real size (required by Topaz create_request)
    try:
        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.get(video_url, follow_redirects=True)
            resp.raise_for_status()
            video_bytes = resp.content
        size = len(video_bytes)
    except Exception as exc:
        logger.error("Worker: failed to download video for enhance {id} — {exc}", id=task.id, exc=str(exc))
        return

    async with AsyncSessionLocal() as db:
        from src.repositories import user as user_repo
        from src.core.settings import settings as _settings
        user = await user_repo.get_by_username(db, _settings.admin_username)
        enhance_task = await enhance_repo.create(
            db,
            user_id=user.id,
            source_url=video_url,
            source_width=width,
            source_height=height,
            source_fps=float(fps),
            source_duration=float(duration),
            source_frame_count=frame_count,
            source_size=size,
            output_resolution=out_res,
            generation_task_id=task.id,
            local_path=task.local_path,
        )

    logger.info(
        "Worker: enhance queued for task {id} | {w}x{h} → {res} size={size}",
        id=task.id, w=width, h=height, res=out_res, size=size,
    )

    # Submit immediately while we still have video_bytes in memory
    await _submit_enhance(enhance_task, video_bytes)


async def _submit_enhance(task, video_bytes: bytes) -> None:
    """Run the full Topaz submission flow for one EnhanceTask given pre-downloaded video bytes."""
    try:
        request_id, estimates = await topaz_client.create_request(
            source_width=task.source_width,
            source_height=task.source_height,
            source_fps=task.source_fps,
            source_duration=task.source_duration,
            source_frame_count=task.source_frame_count,
            source_size=task.source_size,
            source_container=task.source_container,
            output_resolution=task.output_resolution,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.error("Worker: enhance create_request failed {id} — {exc}", id=task.id, exc=str(exc))
        async with AsyncSessionLocal() as db:
            await enhance_repo.update(db, task.id, status="failed", error_message=str(exc))
        return

    async with AsyncSessionLocal() as db:
        await enhance_repo.update(db, task.id, request_id=request_id, status="accepted")

    try:
        upload_id, upload_urls = await topaz_client.accept_request(request_id)
    except Exception as exc:
        logger.error("Worker: enhance accept failed {rid} — {exc}", rid=request_id, exc=str(exc))
        async with AsyncSessionLocal() as db:
            await enhance_repo.update(db, task.id, status="failed", error_message=str(exc))
        return

    try:
        upload_results = await topaz_client.upload_parts(video_bytes, upload_urls)
        await topaz_client.complete_upload(request_id, upload_id, upload_results)
    except Exception as exc:
        logger.error("Worker: enhance upload failed {rid} — {exc}", rid=request_id, exc=str(exc))
        async with AsyncSessionLocal() as db:
            await enhance_repo.update(db, task.id, status="failed", error_message=str(exc))
        return

    # Store cost estimate (take max of range, e.g. [1, 2] → 2)
    cost = estimates.get("cost")
    cost_credits: int | None = None
    if isinstance(cost, list) and cost:
        cost_credits = int(max(cost))
    elif isinstance(cost, (int, float)):
        cost_credits = int(cost)

    async with AsyncSessionLocal() as db:
        await enhance_repo.update(db, task.id, status="processing", cost_credits=cost_credits)

    logger.info(
        "Worker: enhance submitted | id={id} request_id={rid} cost={cost}",
        id=task.id, rid=request_id, cost=cost_credits,
    )


async def _submit_queued_enhance() -> None:
    """Pick up queued enhance tasks that weren't submitted inline (e.g. after restart)."""
    async with AsyncSessionLocal() as db:
        queued = await enhance_repo.list_queued(db)

    if not queued:
        return

    logger.debug("Worker: submitting {n} queued enhance task(s)", n=len(queued))

    for task in queued:
        try:
            async with httpx.AsyncClient(timeout=120) as http:
                resp = await http.get(task.source_url, follow_redirects=True)
                resp.raise_for_status()
                video_bytes = resp.content
            # Update size in case it was 0 when queued
            actual_size = len(video_bytes)
            if actual_size != task.source_size:
                async with AsyncSessionLocal() as db:
                    await enhance_repo.update(db, task.id, source_size=actual_size)
                task.source_size = actual_size
        except Exception as exc:
            logger.error("Worker: enhance download failed {id} — {exc}", id=task.id, exc=str(exc))
            async with AsyncSessionLocal() as db:
                await enhance_repo.update(db, task.id, status="failed", error_message=str(exc))
            continue

        await _submit_enhance(task, video_bytes)


async def _poll_enhance() -> None:
    """Poll Topaz for status of all in-progress enhance tasks."""
    async with AsyncSessionLocal() as db:
        processing = await enhance_repo.list_processing(db)

    if not processing:
        return

    logger.debug("Worker: polling {n} enhance task(s)", n=len(processing))

    for task in processing:
        try:
            result = await topaz_client.get_job(task.request_id)
        except Exception as exc:
            logger.error("Worker: enhance poll failed {rid} — {exc}", rid=task.request_id, exc=exc)
            continue

        fields: dict = {"status": result.status, "progress": result.progress}

        if result.status == "complete":
            fields.update(
                download_url=result.download_url,
                expires_in_ms=result.expires_in_ms,
            )
            # Write upscaled URL back to the parent generation task
            if result.download_url and task.generation_task_id:
                async with AsyncSessionLocal() as db:
                    await generation_repo.update(db, task.generation_task_id, video_url=result.download_url)
                logger.info(
                    "Worker: enhance url written to generation {id}",
                    id=task.generation_task_id,
                )
            # Download upscaled video — overwrite local_path (replaces original)
            if result.download_url and task.local_path:
                await _download_video(result.download_url, task.local_path)
                logger.success(
                    "Worker: enhance complete | saved to {path}",
                    path=task.local_path,
                )
        elif result.status == "failed":
            fields["error_message"] = result.error_message

        async with AsyncSessionLocal() as db:
            await enhance_repo.update(db, task.id, **fields)


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
            await _submit_queued_enhance()
            await _poll_enhance()
        except Exception as exc:
            logger.error("Worker: unexpected error — {exc}", exc=exc)
        await asyncio.sleep(settings.worker_poll_interval)
