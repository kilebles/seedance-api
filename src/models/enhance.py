from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class EnhanceTask(Base):
    __tablename__ = "enhance_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Topaz requestId (UUID string)
    request_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    # Source generation task (optional — None for standalone enhance)
    generation_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("generation_tasks.id"), nullable=True, index=True)

    # --- input ---
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    source_width: Mapped[int] = mapped_column(Integer, nullable=False)
    source_height: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fps: Mapped[float] = mapped_column(Float, nullable=False)
    source_duration: Mapped[float] = mapped_column(Float, nullable=False)
    source_frame_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_size: Mapped[int] = mapped_column(Integer, nullable=False)
    source_container: Mapped[str] = mapped_column(String(16), nullable=False, default="mp4")
    output_resolution: Mapped[str] = mapped_column(String(8), nullable=False)  # "1080p" | "4k"

    # --- lifecycle ---
    # queued → accepted → processing → complete | failed | canceled
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- output path (same as generation local_path when coming from pipeline) ---
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- result ---
    download_url: Mapped[str | None] = mapped_column(String, nullable=True)
    expires_in_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- billing ---
    # Topaz credit cost (actual, from estimates after accept). Nullable for old rows.
    cost_credits: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- error ---
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
