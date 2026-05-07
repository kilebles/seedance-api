from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .content import ContentItem


class AspectRatio(str, Enum):
    ratio_16_9 = "16:9"
    ratio_9_16 = "9:16"
    ratio_1_1 = "1:1"
    ratio_4_3 = "4:3"
    ratio_3_4 = "3:4"
    ratio_21_9 = "21:9"
    adaptive = "adaptive"


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
    ratio: AspectRatio = Field(default=AspectRatio.adaptive)
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


class TaskResultResponse(BaseModel):
    id: str
    status: TaskStatus
    model: str | None = None
    created_at: int | None = None
    updated_at: int | None = None
    content: TaskContent | None = None
    # video specs (top-level in API response)
    ratio: str | None = None
    resolution: str | None = None
    duration: int | None = None
    framespersecond: int | None = None
    seed: int | None = None
    generate_audio: bool | None = None
    error: dict | None = None
