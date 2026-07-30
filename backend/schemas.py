from pydantic import BaseModel
from typing import Optional
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
    value: int
    timestamp: int

class CommonResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Optional[dict] = None