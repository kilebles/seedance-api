from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base


class ImageTask(Base):
    __tablename__ = "image_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    # --- input params ---
    model: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    size_requested: Mapped[str | None] = mapped_column(String(32), nullable=True)
    watermark: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seed_requested: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- lifecycle ---
    # succeeded | failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="succeeded", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- result ---
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_size: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- billing ---
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- error ---
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
