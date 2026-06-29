from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ImageGenerationRequest(BaseModel):
    model: str = Field(
        default="seedream-5-0-260128",
        description="Seedream model ID for image generation",
    )
    prompt: str = Field(description="Text prompt for image generation")
    # single URL/base64, or list of URLs/base64 for multi-image reblending
    image: str | list[str] | None = Field(default=None)
    size: str | None = Field(default=None, description="e.g. '2048x2048', '2K', '3K', '4K'")
    output_format: str = Field(default="jpeg", description="'jpeg' or 'png'")
    watermark: bool = Field(default=False)
    seed: int | None = Field(default=None, ge=-1, le=2147483647)


class ImageTaskDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID

    # input
    model: str
    prompt: str
    size_requested: str | None
    watermark: bool
    seed_requested: int | None

    # lifecycle
    status: str
    created_at: datetime
    updated_at: datetime

    # result
    image_url: str | None
    image_size: str | None
    output_tokens: int | None
    total_tokens: int | None

    # error
    error_code: str | None
    error_message: str | None
