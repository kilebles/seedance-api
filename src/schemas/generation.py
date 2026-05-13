from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .content import ContentItem


class AspectRatio(str, Enum):
    ratio_16_9 = "16:9"
    ratio_9_16 = "9:16"
    ratio_1_1 = "1:1"
    ratio_4_3 = "4:3"
    ratio_3_4 = "3:4"
    ratio_21_9 = "21:9"


class Resolution(str, Enum):
    p480 = "480p"
    p720 = "720p"


class GenerationRequest(BaseModel):
    model: str = Field(
        default="dreamina-seedance-2-0-fast-260128",
        description="Seedance model ID",
    )
    content: list[ContentItem] = Field(
        description="Ordered list of content items (text prompt + optional media references)"
    )
    generate_audio: bool = Field(default=True)
    ratio: AspectRatio = Field(default=AspectRatio.ratio_16_9)
    resolution: Resolution = Field(default=Resolution.p720)
    # [4, 15] seconds, or -1 for smart selection
    duration: int | None = Field(default=None, ge=-1, le=15)
    seed: int | None = Field(default=None, ge=-1, le=4294967295)
    watermark: bool = Field(default=False)
    callback_url: str | None = Field(default=None)
    return_last_frame: bool = Field(default=False)
    execution_expires_after: int | None = Field(default=None, ge=3600, le=259200)
    safety_identifier: str | None = Field(default=None, max_length=64)


class TaskStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    expired = "expired"


class GenerationTaskResponse(BaseModel):
    id: str
    status: TaskStatus | None = None
    model: str | None = None
    created_at: int | None = None


class TaskContent(BaseModel):
    video_url: str | None = None
    last_frame_image_url: str | None = None


class TaskUsage(BaseModel):
    completion_tokens: int | None = None
    total_tokens: int | None = None


# Raw BytePlus API response — used internally by seedance_client
class TaskResultResponse(BaseModel):
    id: str
    status: TaskStatus
    model: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    content: TaskContent | None = None
    ratio: str | None = None
    resolution: str | None = None
    duration: int | None = None
    framespersecond: int | None = None
    seed: int | None = None
    generate_audio: bool | None = None
    usage: TaskUsage | None = None
    error: dict | None = None


# API response schema backed by our DB record
class TaskDB(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    external_id: str | None
    user_id: uuid.UUID

    # input
    model: str
    ratio_requested: str
    resolution_requested: str
    duration_requested: int | None
    generate_audio: bool
    watermark: bool
    seed_requested: int | None
    content_items: list

    # lifecycle
    status: str
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # result
    video_url: str | None
    last_frame_url: str | None
    duration_actual: int | None
    ratio_actual: str | None
    resolution_actual: str | None
    seed_actual: int | None
    framespersecond: int | None

    # billing
    completion_tokens: int | None
    total_tokens: int | None

    # error
    error_code: str | None
    error_message: str | None

    # batch
    name: str | None = None
    local_path: str | None = None
    batch_id: str | None = None
    batch_order: int | None = None
