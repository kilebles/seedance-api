from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class GenerationTask(Base):
    __tablename__ = "generation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # BytePlus task ID (cgt-xxx), appears after successful submit
    external_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # --- input params ---
    model: Mapped[str] = mapped_column(String, nullable=False)
    ratio_requested: Mapped[str] = mapped_column(String, nullable=False)
    resolution_requested: Mapped[str] = mapped_column(String, nullable=False)
    duration_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generate_audio: Mapped[bool] = mapped_column(Boolean, nullable=False)
    watermark: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seed_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # [{type, role, url}] — base64 stripped, only references stored
    content_items: Mapped[list] = mapped_column(JSONB, nullable=False)

    # --- lifecycle ---
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- result ---
    video_url: Mapped[str | None] = mapped_column(String, nullable=True)
    last_frame_url: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ratio_actual: Mapped[str | None] = mapped_column(String(16), nullable=True)
    resolution_actual: Mapped[str | None] = mapped_column(String(16), nullable=True)
    seed_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    framespersecond: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- billing ---
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- error ---
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- batch ---
    name: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    local_path: Mapped[str | None] = mapped_column(String, nullable=True)
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    batch_order: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
