from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx
from loguru import logger

from src.core.settings import settings

_BASE_URL = "https://api.topazlabs.com/video/"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
_UPLOAD_TIMEOUT = httpx.Timeout(300.0, connect=10.0)  # large files

OutputResolution = Literal["1080p", "4k"]

_RESOLUTION_MAP: dict[OutputResolution, tuple[int, int]] = {
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}

# Terminal statuses per Topaz docs
TERMINAL_STATUSES = {"complete", "canceled", "failed"}
RUNNING_STATUSES = {"requested", "accepted", "initializing", "preprocessing", "processing", "postprocessing", "canceling"}


@dataclass
class TopazJobResult:
    request_id: str
    status: str          # one of TERMINAL_STATUSES | RUNNING_STATUSES
    progress: float      # 0–100
    download_url: str | None    # set only when status == "complete"
    expires_in_ms: int | None   # TTL in ms
    error_message: str | None   # set on "failed"
    raw: dict[str, Any]


def _make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "X-API-Key": settings.topaz_api_key,
            "Content-Type": "application/json",
        },
        timeout=_TIMEOUT,
    )


async def check_connection() -> dict[str, Any]:
    """Validate API key — Topaz has no ping endpoint.
    400 INVALID_INPUT = key accepted. Raises on 401/403/5xx.
    """
    async with _make_client() as client:
        response = await client.post("", json={"model": "prob-4", "filters": []})

    logger.debug(
        "Topaz connection check | status={status} body={body}",
        status=response.status_code,
        body=response.text[:500],
    )

    if response.status_code == 400:
        data = response.json()
        if data.get("errorCode") == "INVALID_INPUT":
            logger.success("Topaz API key valid (INVALID_INPUT on empty request is expected)")
            return data

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "Topaz API error | status={status} body={body}",
            status=response.status_code,
            body=response.text,
        )
        raise

    return response.json()


async def create_request(
    *,
    source_width: int,
    source_height: int,
    source_fps: float,
    source_duration: float,
    source_frame_count: int,
    source_size: int,
    source_container: str = "mp4",
    output_resolution: OutputResolution = "4k",
    video_type: Literal["Progressive", "Interlaced", "ProgressiveInterlaced"] = "Progressive",
    auto: Literal["Auto", "Manual", "Relative"] = "Auto",
    compression: float = 0.0,
    details: float = 0.0,
    noise: float = 0.0,
    halo: float = 0.0,
    blur: float = 0.0,
    output_container: str = "mp4",
    audio_transfer: Literal["Copy", "Convert", "None"] = "Copy",
    audio_codec: str = "aac",
) -> tuple[str, dict[str, Any]]:
    """Step 1: register the job with Topaz, get requestId + cost/time estimates.

    Returns (request_id, estimates_dict).
    Does NOT consume credits — credits are reserved on PATCH /accept.
    """
    out_w, out_h = _RESOLUTION_MAP[output_resolution]

    filter_params: dict[str, Any] = {
        "model": "prob-4",
        "output_resolution": output_resolution,
    }
    if compression != 0.0:
        filter_params["compression"] = compression
    if details != 0.0:
        filter_params["details"] = details
    if noise != 0.0:
        filter_params["noise"] = noise
    if halo != 0.0:
        filter_params["halo"] = halo
    if blur != 0.0:
        filter_params["blur"] = blur

    payload: dict[str, Any] = {
        "source": {
            "container": source_container,
            "size": source_size,
            "duration": source_duration,
            "frameCount": source_frame_count,
            "frameRate": source_fps,
            "resolution": {"width": source_width, "height": source_height},
        },
        "filters": [filter_params],
        "output": {
            "container": output_container,
            "resolution": {"width": source_width, "height": source_height},
            "frameRate": source_fps,
            "audioTransfer": audio_transfer,
            "audioCodec": audio_codec,
            "dynamicCompressionLevel": "High",
        },
    }

    logger.info(
        "Topaz create_request | {w}x{h} → {res} fps={fps} dur={dur}s",
        w=source_width, h=source_height, res=output_resolution,
        fps=source_fps, dur=source_duration,
    )
    logger.debug("Topaz create_request payload: {payload}", payload=payload)

    async with _make_client() as client:
        response = await client.post("", json=payload)

    logger.debug(
        "Topaz create_request response | status={status} body={body}",
        status=response.status_code,
        body=response.text[:500],
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "Topaz create_request error | status={status} body={body}",
            status=response.status_code,
            body=response.text,
        )
        raise

    data = response.json()
    request_id: str = data["requestId"]
    estimates = data.get("estimates", {})
    logger.success(
        "Topaz request created | request_id={rid} cost={cost} time={time}s",
        rid=request_id,
        cost=estimates.get("cost"),
        time=estimates.get("time"),
    )
    return request_id, estimates


async def accept_request(request_id: str) -> tuple[str, list[str]]:
    """Step 2: reserve credits and get S3 multipart upload URLs.

    Returns (upload_id, [url1, url2, ...]).
    Split the source video into len(urls) equal byte ranges and PUT each part.
    """
    async with _make_client() as client:
        response = await client.patch(f"{request_id}/accept")

    logger.debug(
        "Topaz accept | request_id={rid} status={status} body={body}",
        rid=request_id,
        status=response.status_code,
        body=response.text[:500],
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "Topaz accept error | request_id={rid} status={status} body={body}",
            rid=request_id,
            status=response.status_code,
            body=response.text,
        )
        raise

    data = response.json()
    upload_id: str = data["uploadId"]
    urls: list[str] = data["urls"]
    logger.info(
        "Topaz accept OK | request_id={rid} upload_id={uid} parts={n}",
        rid=request_id, uid=upload_id, n=len(urls),
    )
    return upload_id, urls


async def upload_parts(video_bytes: bytes, upload_urls: list[str]) -> list[dict[str, Any]]:
    """Step 3: PUT video parts to S3 presigned URLs.

    Splits video_bytes evenly across upload_urls.
    Returns list of {partNum, eTag} pairs needed for complete_upload.
    """
    n = len(upload_urls)
    chunk_size = (len(video_bytes) + n - 1) // n  # ceiling division
    results: list[dict[str, Any]] = []

    async with httpx.AsyncClient(timeout=_UPLOAD_TIMEOUT) as client:
        for i, url in enumerate(upload_urls, start=1):
            chunk = video_bytes[(i - 1) * chunk_size: i * chunk_size]
            logger.debug(
                "Topaz upload part {i}/{n} | size={size}",
                i=i, n=n, size=len(chunk),
            )
            response = await client.put(url, content=chunk, headers={"Content-Type": "application/octet-stream"})
            response.raise_for_status()
            etag = response.headers.get("ETag", "")
            results.append({"partNum": i, "eTag": etag})
            logger.debug("Topaz uploaded part {i}/{n} | etag={etag}", i=i, n=n, etag=etag)

    logger.info("Topaz upload complete | {n} parts", n=n)
    return results


async def complete_upload(
    request_id: str,
    upload_id: str,
    upload_results: list[dict[str, Any]],
    md5_hash: str | None = None,
) -> None:
    """Step 4: confirm multipart upload and start processing."""
    body: dict[str, Any] = {"uploadId": upload_id, "uploadResults": upload_results}
    if md5_hash:
        body["md5Hash"] = md5_hash

    async with _make_client() as client:
        response = await client.patch(f"{request_id}/complete-upload/", json=body)

    logger.debug(
        "Topaz complete_upload | request_id={rid} status={status} body={body}",
        rid=request_id,
        status=response.status_code,
        body=response.text[:300],
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "Topaz complete_upload error | request_id={rid} status={status} body={body}",
            rid=request_id,
            status=response.status_code,
            body=response.text,
        )
        raise

    logger.success("Topaz processing started | request_id={rid}", rid=request_id)


async def get_job(request_id: str) -> TopazJobResult:
    """Poll job status. Call repeatedly until result.status in TERMINAL_STATUSES."""
    async with _make_client() as client:
        response = await client.get(f"{request_id}/status")

    logger.debug(
        "Topaz get_job | request_id={rid} status={status} body={body}",
        rid=request_id,
        status=response.status_code,
        body=response.text[:500],
    )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError:
        logger.error(
            "Topaz get_job error | request_id={rid} status={status} body={body}",
            rid=request_id,
            status=response.status_code,
            body=response.text,
        )
        raise

    data = response.json()
    job_status: str = data.get("status", "")
    progress: float = data.get("progress", 0.0)

    download_url: str | None = None
    expires_in_ms: int | None = None
    if "download" in data and data["download"]:
        dl = data["download"]
        download_url = dl.get("url")
        expires_in_ms = dl.get("expiresIn")

    error_message: str | None = data.get("message") if job_status == "failed" else None

    if job_status == "complete":
        logger.success(
            "Topaz job complete | request_id={rid} url={url}",
            rid=request_id, url=download_url,
        )
    elif job_status == "failed":
        logger.error(
            "Topaz job failed | request_id={rid} message={msg}",
            rid=request_id, msg=error_message,
        )
    else:
        logger.info(
            "Topaz job status | request_id={rid} status={status} progress={progress:.1f}%",
            rid=request_id, status=job_status, progress=progress,
        )

    return TopazJobResult(
        request_id=request_id,
        status=job_status,
        progress=progress,
        download_url=download_url,
        expires_in_ms=expires_in_ms,
        error_message=error_message,
        raw=data,
    )
