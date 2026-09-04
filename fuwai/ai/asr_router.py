"""ASR router for mounting into the team's existing FastAPI backend."""

from __future__ import annotations

import os
import secrets
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict

from asr.asr_service import transcribe_event


load_dotenv(Path(__file__).with_name(".env"))
MAX_AUDIO_BYTES = int(os.getenv("ASR_MAX_AUDIO_BYTES", str(500 * 1024 * 1024)))
ALLOWED_SUFFIXES = {".mp3", ".wav", ".pcm", ".opus", ".flac", ".ogg", ".speex", ".m4a", ".aac"}


class ASRResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    event_id: str
    status: str
    transcript: str | None
    language: str
    provider: str
    duration_ms: int | None
    error_code: str | None
    error_message: str | None
    schema_version: int


router = APIRouter(prefix="/internal/ai", tags=["internal-ai"])


@router.post("/asr", response_model=ASRResponse)
async def asr(
    file: UploadFile = File(...),
    event_id: str = Form(...),
    source: str = Form(...),
    consent: bool = Form(...),
    language: str = Form("zh-CN"),
    recorded_at: str | None = Form(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> ASRResponse:
    del recorded_at
    expected_key = os.getenv("ASR_INTERNAL_API_KEY", "")
    if not expected_key:
        raise HTTPException(status_code=500, detail="ASR 服务尚未配置内部鉴权")
    if not x_api_key or not secrets.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="无效的 X-API-Key")
    if not event_id.strip():
        raise HTTPException(status_code=422, detail="event_id 不能为空")
    if language != "zh-CN":
        raise HTTPException(status_code=422, detail="MVP 仅支持 language=zh-CN")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="不支持的音频格式")

    temp_path: Path | None = None
    total = 0
    try:
        with tempfile.NamedTemporaryFile(prefix="gongzai-asr-", suffix=suffix, delete=False) as temp:
            temp_path = Path(temp.name)
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_AUDIO_BYTES:
                    raise HTTPException(status_code=413, detail="音频文件超过大小限制")
                temp.write(chunk)
        result = await run_in_threadpool(
            transcribe_event,
            temp_path,
            event_id.strip(),
            source,
            consent,
            language,
        )
        return ASRResponse.model_validate(result)
    finally:
        await file.close()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
