"""Pydantic models mirroring the versioned AI integration contract."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AIMomentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1, max_length=10_000)
    voice_id: Optional[str] = Field(default=None, max_length=128)
    event_id: Optional[str] = Field(default=None, max_length=128)
    recorded_at: Optional[datetime] = None
    bpm: Optional[int] = Field(default=None, ge=30, le=240)
    consent: bool = Field(default=False)
    schema_version: int = Field(default=1, ge=1, le=1)


class AIMomentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=5)
    suggested_replies: list[str] = Field(default_factory=list, max_length=3)
    safety_flags: list[str] = Field(default_factory=list)
    ai_status: str
    schema_version: int = 1
    prompt_version: str = "moment-v5"


class AIErrorResponse(BaseModel):
    code: str
    message: str
    retryable: bool
    schema_version: int = 1
