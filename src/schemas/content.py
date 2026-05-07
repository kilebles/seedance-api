from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class TextContent(BaseModel):
    type: Literal["text"]
    text: str


class ImageUrl(BaseModel):
    # Accepts HTTP URL, Base64 data URI (data:image/...;base64,...), or asset:// URI
    url: str


class ImageContent(BaseModel):
    type: Literal["image_url"]
    image_url: ImageUrl
    # first_frame / last_frame: image-to-video; reference_image: multimodal reference
    role: Literal["first_frame", "last_frame", "reference_image"] | None = None


class VideoUrl(BaseModel):
    # Accepts HTTP URL or asset:// URI
    url: str


class VideoContent(BaseModel):
    type: Literal["video_url"]
    video_url: VideoUrl
    role: Literal["reference_video"] = "reference_video"


class AudioUrl(BaseModel):
    # Accepts HTTP URL, Base64 data URI (data:audio/...;base64,...), or asset:// URI
    url: str


class AudioContent(BaseModel):
    type: Literal["audio_url"]
    audio_url: AudioUrl
    role: Literal["reference_audio"] = "reference_audio"


ContentItem = Annotated[
    Union[TextContent, ImageContent, VideoContent, AudioContent],
    Field(discriminator="type"),
]
