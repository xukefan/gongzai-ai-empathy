from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime

class HeartbeatSendRequest(BaseModel):
    sender_id: str
    receiver_id: str
    bpm: int
    pattern: Optional[str] = None

class HeartbeatSendResponse(BaseModel):
    event_id: str
    status: str
    message: Optional[str] = None

class DeviceBindRequest(BaseModel):
    user_id: str
    device_id: str
    product_id: str = "coglink_v1"

class DeviceBindResponse(BaseModel):
    status: str
    message: Optional[str] = None

class TimelineItem(BaseModel):
    id: str
    title: Optional[str]
    summary: Optional[str]
    bpm: Optional[int]
    voice_url: Optional[str]
    created_at: datetime
    response_status: Optional[str]

class TimelineResponse(BaseModel):
    moments: list[TimelineItem]

class TuyaWebhookRequest(BaseModel):
    device_id: str
    dp_id: int
    value: Any
    timestamp: int

class CommonResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Optional[dict] = None


class GenerateMomentRequest(BaseModel):
    """A single user-confirmed transcript and its record metadata."""

    user_id: str = Field(min_length=1, max_length=128)
    # `content` remains the public field name for compatibility. It must be
    # the text the user has checked and approved after ASR.
    content: Optional[str] = Field(default=None, min_length=1, max_length=10_000)
    consent: bool = False
    voice_id: Optional[str] = Field(default=None, max_length=128)
    event_id: Optional[str] = Field(default=None, max_length=128)
    raw_transcript: Optional[str] = Field(default=None, max_length=10_000)
    bpm: Optional[int] = Field(default=None, ge=30, le=240)
    recorded_at: Optional[datetime] = None
    source: Optional[str] = Field(default=None, pattern="^(watch|iphone|pendant)$")
    image_urls: list[str] = Field(default_factory=list, max_length=9)
    user_note: Optional[str] = Field(default=None, max_length=2_000)
    schema_version: int = Field(default=1, ge=1, le=1)
