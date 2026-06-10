from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from loguru import logger

from src.core.settings import settings

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_DIR = Path("output/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED = {"video/mp4", "video/webm", "video/quicktime", "image/jpeg", "image/png", "image/webp"}
_MAX_SIZE = 500 * 1024 * 1024  # 500 MB


@router.post("")
async def upload_file(file: UploadFile) -> dict:
    if file.content_type not in _ALLOWED:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")

    data = await file.read()
    if len(data) > _MAX_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 500 MB)")

    ext = Path(file.filename or "file").suffix or ".bin"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = UPLOAD_DIR / filename
    path.write_bytes(data)

    logger.info("Upload saved | file={f} size={s}", f=filename, s=len(data))
    return {"url": f"{settings.public_base_url}/uploads/{filename}"}


@router.get("/{filename}", include_in_schema=False)
async def serve_file(filename: str) -> FileResponse:
    path = UPLOAD_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    # prevent path traversal
    if UPLOAD_DIR not in path.parents and path.parent != UPLOAD_DIR:
        raise HTTPException(status_code=400)
    return FileResponse(path)
