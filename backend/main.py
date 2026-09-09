from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
from sqlalchemy.orm import Session
from typing import List
import uuid
import base64
import hashlib
import hmac
import subprocess
import time
from pathlib import Path

from database import get_db, engine
from models import Base, User, Relationship, Device, HeartbeatEvent, VoiceRecord, Moment, Response, DoNotDisturbSetting
from schemas import *
from tuya_client import TuyaClient
from config import Config
from ai_service import AIServiceError, generate_diary
from migrations import migrate_schema
from asr.asr_service import transcribe_event
from asr_router import router as asr_router
from auth import create_access_token, get_current_user, hash_password, require_user_id, verify_password

Base.metadata.create_all(bind=engine)
migrate_schema(engine)

app = FastAPI(title="共感挂件后端API", version="1.0")
app.include_router(asr_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

tuya = TuyaClient()
VOICE_STORAGE_ROOT = (Path(__file__).resolve().parent / Config.VOICE_STORAGE_DIR).resolve()
PENDANT_AUDIO_ROOT = (Path(__file__).resolve().parent / Config.PENDANT_AUDIO_DIR).resolve()
ALLOWED_VOICE_EXTENSIONS = {".m4a", ".wav", ".mp3", ".aac"}


def _transcode_for_pendant(source_path: Path, output_path: Path) -> tuple[bool, str | None]:
    """Create a small MP3 stream without changing the private original."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        Config.FFMPEG_BINARY,
        "-hide_banner", "-loglevel", "error",
        "-y", "-i", str(source_path),
        "-vn", "-ac", "1", "-ar", str(Config.PENDANT_AUDIO_SAMPLE_RATE),
        "-c:a", "libmp3lame", "-b:a", Config.PENDANT_AUDIO_BITRATE,
        "-f", "mp3", str(output_path),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=Config.PENDANT_AUDIO_TRANSCODE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return False, "ffmpeg is not installed on the server"
    except subprocess.TimeoutExpired:
        return False, "audio conversion timed out"
    if completed.returncode != 0 or not output_path.is_file() or output_path.stat().st_size == 0:
        return False, "audio conversion failed"
    return True, None


def _playback_ticket_payload(device_id: str, event_id: str, voice_id: str, expires_at: int) -> str:
    return f"{device_id}.{event_id}.{voice_id}.{expires_at}"


def _issue_playback_ticket(device_id: str, event_id: str, voice_id: str) -> str | None:
    secret = Config.PENDANT_PLAYBACK_TICKET_SECRET
    if not secret:
        return None
    expires_at = int(time.time()) + Config.PENDANT_PLAYBACK_TICKET_TTL_SECONDS
    payload = _playback_ticket_payload(device_id, event_id, voice_id, expires_at)
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{expires_at}.{signature}"


def _verify_playback_ticket(ticket: str, device_id: str, event_id: str, voice_id: str) -> bool:
    secret = Config.PENDANT_PLAYBACK_TICKET_SECRET
    if not secret or not ticket:
        return False
    try:
        expires_text, signature = ticket.split(".", 1)
        expires_at = int(expires_text)
    except (ValueError, AttributeError):
        return False
    if expires_at < int(time.time()):
        return False
    payload = _playback_ticket_payload(device_id, event_id, voice_id, expires_at)
    expected = base64.urlsafe_b64encode(
        hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")
    return hmac.compare_digest(signature, expected)


def _pendant_audio_url(event: HeartbeatEvent, device_id: str, voice: VoiceRecord | None) -> str | None:
    if voice is None or voice.pendant_audio_status != "ready" or not voice.pendant_file_url:
        return None
    ticket = _issue_playback_ticket(device_id, event.event_id, voice.id)
    if not ticket or not Config.PUBLIC_API_BASE_URL:
        return None
    return (
        f"{Config.PUBLIC_API_BASE_URL}/api/pendant/media/{voice.id}.mp3"
        f"?device_id={device_id}&event_id={event.event_id}&ticket={ticket}"
    )

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "coglink-backend"}


def _auth_user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@app.post("/api/auth/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    username = req.username.strip()
    if len(username) < 3 or len(username) > 50:
        raise HTTPException(status_code=422, detail="用户名长度需要在3到50个字符之间")
    if len(req.password) < 8 or len(req.password) > 128:
        raise HTTPException(status_code=422, detail="密码长度需要在8到128个字符之间")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=409, detail="用户名已存在")

    # The legacy User table has a required phone column. For this prototype
    # phone verification is intentionally omitted. A short deterministic
    # internal value keeps old databases compatible without storing a fake
    # phone number or exceeding the column's VARCHAR(20) limit.
    phone = (req.phone or f"u_{hashlib.sha256(username.encode('utf-8')).hexdigest()[:18]}").strip()
    if len(phone) > 20:
        raise HTTPException(status_code=422, detail="手机号长度不能超过20个字符")
    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=409, detail="手机号已存在")

    user = User(username=username, phone=phone, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    token, expires_at = create_access_token(user)
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthUserResponse(**_auth_user_payload(user)),
    )


@app.post("/api/auth/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username.strip()).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token, expires_at = create_access_token(user)
    return AuthResponse(
        access_token=token,
        expires_at=expires_at,
        user=AuthUserResponse(**_auth_user_payload(user)),
    )


@app.get("/api/auth/me", response_model=AuthUserResponse)
def current_user_profile(current_user: User = Depends(get_current_user)):
    return AuthUserResponse(**_auth_user_payload(current_user))

@app.post("/api/heartbeat/send", response_model=HeartbeatSendResponse)
def send_heartbeat(
    req: HeartbeatSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, req.sender_id)
    if req.receiver_id == req.sender_id:
        raise HTTPException(status_code=422, detail="发送方和接收方不能相同")
    if req.voice_id:
        voice = db.query(VoiceRecord).filter(VoiceRecord.id == req.voice_id).first()
        if not voice:
            raise HTTPException(status_code=404, detail="voice not found")
        if voice.user_id != req.sender_id:
            raise HTTPException(status_code=403, detail="voice does not belong to sender")

    event_id = str(uuid.uuid4())
    
    event = HeartbeatEvent(
        event_id=event_id,
        sender_id=req.sender_id,
        receiver_id=req.receiver_id,
        bpm=req.bpm,
        pattern=req.pattern,
        voice_id=req.voice_id,
        delivery_mode=Config.PENDANT_DELIVERY_MODE,
    )
    db.add(event)
    db.commit()
    
    device = db.query(Device).filter(Device.user_id == req.receiver_id).first()
    if not device:
        event.status = "failed"
        db.commit()
        return HeartbeatSendResponse(
            event_id=event_id,
            status="error",
            message="接收方未绑定设备"
        )
    
    if Config.PENDANT_DELIVERY_MODE != "tuya":
        return HeartbeatSendResponse(
            event_id=event_id,
            status="ok",
            message="已进入挂件待接收队列"
        )

    try:
        tuya.send_command(device.device_id, Config.TUYA_BPM_CODE, req.bpm)
        if req.pattern:
            tuya.send_command(device.device_id, Config.TUYA_PATTERN_CODE, req.pattern)
        tuya.send_command(device.device_id, Config.TUYA_TRIGGER_CODE, True)
        # 下发成功后，把事件状态更新为 "delivered"
        event.status = "delivered"
        db.commit()
        
        return HeartbeatSendResponse(
            event_id=event_id,
            status="ok",
            message="已下发到挂件"
        )
    except Exception as e:
        event.status = "failed"
        db.commit()
        return HeartbeatSendResponse(
            event_id=event_id,
            status="error",
            message=f"涂鸦下发失败: {str(e)}"
        )


def _device_or_404(device_id: str, db: Session) -> Device:
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="device is not bound")
    return device


def _verify_pendant_token(x_pendant_token: str | None) -> None:
    if Config.PENDANT_API_TOKEN and x_pendant_token != Config.PENDANT_API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid pendant token")


@app.get("/api/pendant/events/next")
def get_next_pendant_event(
    device_id: str,
    x_pendant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return the oldest direct event and keep it queued until the pendant ACKs it."""
    _verify_pendant_token(x_pendant_token)
    device = _device_or_404(device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.receiver_id == device.user_id,
        HeartbeatEvent.delivery_mode == "direct",
        # A direct pendant claims an event exactly once. It immediately sends a
        # playback ACK; later retries are handled by the client upload queue.
        HeartbeatEvent.status == "created",
    ).order_by(HeartbeatEvent.sent_at.asc()).first()
    if not event:
        return {"status": "empty", "event": None}

    voice = db.query(VoiceRecord).filter(VoiceRecord.id == event.voice_id).first() if event.voice_id else None
    audio_url = _pendant_audio_url(event, device_id, voice)

    return {
        "status": "ok",
        "event": {
            "event_id": event.event_id,
            "bpm": event.bpm,
            "pattern": event.pattern,
            "voice_id": event.voice_id,
            "audio_url": audio_url,
            "sent_at": event.sent_at.isoformat(),
        },
    }


@app.post("/api/pendant/events/{event_id}/ack")
def acknowledge_pendant_event(
    event_id: str,
    req: PendantAckRequest,
    x_pendant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_pendant_token(x_pendant_token)
    device = _device_or_404(req.device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.event_id == event_id,
        HeartbeatEvent.receiver_id == device.user_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="event not found for this device")
    allowed = {"delivered", "played", "acknowledged"}
    if req.status not in allowed:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(allowed)}")
    event.status = req.status
    db.commit()
    return {"status": "ok", "event_id": event_id, "event_status": event.status}


@app.post("/api/pendant/responses")
def create_pendant_response(
    req: PendantResponseRequest,
    x_pendant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_pendant_token(x_pendant_token)
    device = _device_or_404(req.device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.event_id == req.event_id,
        HeartbeatEvent.receiver_id == device.user_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="event not found for this device")
    if req.response_type not in {"touch", "tap", "voice"}:
        raise HTTPException(status_code=422, detail="unsupported response type")
    response = db.query(Response).filter(
        Response.event_id == req.event_id,
        Response.from_user == device.user_id,
        Response.response_type == req.response_type,
    ).first()
    if not response:
        response = Response(
            event_id=req.event_id,
            from_user=device.user_id,
            response_type=req.response_type,
        )
        db.add(response)
    event.status = "replied"
    db.commit()
    return {"status": "ok", "event_id": req.event_id, "response_type": req.response_type}


@app.post("/api/pendant/voice/upload")
async def upload_pendant_voice_reply(
    device_id: str,
    event_id: str,
    duration_ms: int,
    file: UploadFile = File(...),
    x_pendant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Accept a reply recorded by a bound T5AI pendant.

    The pendant authenticates with its device token; it never receives an end
    user's bearer token.  The event determines the only account that may own
    this reply: the receiver of the original shared moment.
    """
    _verify_pendant_token(x_pendant_token)
    if duration_ms <= 0 or duration_ms > 15_000:
        raise HTTPException(status_code=422, detail="duration_ms must be between 1 and 15000")

    device = _device_or_404(device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.event_id == event_id,
        HeartbeatEvent.receiver_id == device.user_id,
    ).first()
    if not event:
        raise HTTPException(status_code=404, detail="event not found for this device")

    suffix = Path(file.filename or "reply.wav").suffix.lower()
    if suffix != ".wav":
        raise HTTPException(status_code=415, detail="pendant replies must be WAV files")
    content = await file.read(Config.MAX_VOICE_UPLOAD_BYTES + 1)
    if len(content) <= 44:
        raise HTTPException(status_code=422, detail="reply WAV is empty")
    if len(content) > Config.MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="voice file is too large")

    VOICE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}.wav"
    file_path = VOICE_STORAGE_ROOT / stored_filename
    file_path.write_bytes(content)

    voice = VoiceRecord(
        user_id=device.user_id,
        file_url=stored_filename,
        duration=max(1, duration_ms // 1000),
    )
    db.add(voice)
    db.commit()

    pendant_filename = f"{uuid.uuid4()}.mp3"
    pendant_path = PENDANT_AUDIO_ROOT / pendant_filename
    pendant_ready, pendant_error = await run_in_threadpool(
        _transcode_for_pendant, file_path, pendant_path
    )
    if pendant_ready:
        from datetime import datetime
        voice.pendant_file_url = pendant_filename
        voice.pendant_audio_status = "ready"
        voice.pendant_audio_ready_at = datetime.utcnow()
    else:
        voice.pendant_audio_status = "unavailable"
        voice.pendant_audio_error = pendant_error
        if pendant_path.is_file():
            pendant_path.unlink()

    transcription = await run_in_threadpool(
        transcribe_event, file_path, voice.id, "pendant", True, "zh-CN"
    )
    voice.transcript = transcription.get("transcript")
    voice.transcription_status = transcription.get("status", "failed")
    voice.transcription_error = transcription.get("error_message")
    voice.transcription_provider = transcription.get("provider")
    voice.transcription_request_id = transcription.get("request_id")

    response = Response(
        event_id=event.event_id,
        from_user=device.user_id,
        response_type="voice",
        voice_id=voice.id,
    )
    db.add(response)
    event.status = "replied"
    db.commit()
    return {
        "status": "uploaded",
        "event_id": event.event_id,
        "voice_id": voice.id,
        "transcription_status": voice.transcription_status,
        "transcript": voice.transcript,
    }


@app.get("/api/pendant/voice/{voice_id}")
def download_voice_for_pendant(
    voice_id: str,
    device_id: str,
    x_pendant_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_pendant_token(x_pendant_token)
    device = _device_or_404(device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.receiver_id == device.user_id,
        HeartbeatEvent.voice_id == voice_id,
    ).first()
    if not event:
        raise HTTPException(status_code=403, detail="voice is not assigned to this device")
    voice = db.query(VoiceRecord).filter(VoiceRecord.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="voice file not found")
    return FileResponse(file_path, media_type="application/octet-stream", filename=file_path.name)


@app.get("/api/pendant/media/{voice_id}.mp3")
def download_pendant_audio(
    voice_id: str,
    device_id: str,
    event_id: str,
    ticket: str,
    db: Session = Depends(get_db),
):
    """Serve only a ready, event-scoped MP3 to the T5 URL player."""
    if not _verify_playback_ticket(ticket, device_id, event_id, voice_id):
        raise HTTPException(status_code=403, detail="invalid or expired playback ticket")
    device = _device_or_404(device_id, db)
    event = db.query(HeartbeatEvent).filter(
        HeartbeatEvent.event_id == event_id,
        HeartbeatEvent.receiver_id == device.user_id,
        HeartbeatEvent.voice_id == voice_id,
    ).first()
    if not event:
        raise HTTPException(status_code=403, detail="audio is not assigned to this device")
    voice = db.query(VoiceRecord).filter(VoiceRecord.id == voice_id).first()
    if not voice or voice.pendant_audio_status != "ready" or not voice.pendant_file_url:
        raise HTTPException(status_code=404, detail="pendant audio is not ready")
    file_path = (PENDANT_AUDIO_ROOT / voice.pendant_file_url).resolve()
    if PENDANT_AUDIO_ROOT not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="pendant audio file not found")
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=file_path.name,
        headers={"Cache-Control": "private, max-age=60", "Accept-Ranges": "bytes"},
    )

@app.post("/api/devices/bind", response_model=DeviceBindResponse)
def bind_device(
    req: DeviceBindRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, req.user_id)
    existing = db.query(Device).filter(Device.device_id == req.device_id).first()
    if existing:
        return DeviceBindResponse(status="error", message="设备已被绑定")
    
    user_device = db.query(Device).filter(Device.user_id == req.user_id).first()
    if user_device:
        return DeviceBindResponse(status="error", message="该用户已绑定设备")
    
    device = Device(
        user_id=req.user_id,
        device_id=req.device_id,
        product_id=req.product_id
    )
    db.add(device)
    db.commit()
    
    return DeviceBindResponse(status="ok", message="绑定成功")

@app.get("/api/timeline")
def get_timeline(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    events = db.query(HeartbeatEvent).filter(
        (HeartbeatEvent.sender_id == user_id) | 
        (HeartbeatEvent.receiver_id == user_id)
    ).order_by(HeartbeatEvent.sent_at.desc()).limit(20).all()
    
    moments = []
    for event in events:
        response = db.query(Response).filter(Response.event_id == event.event_id).first()
        moments.append({
            "id": event.event_id,
            "title": f"心率 {event.bpm} BPM",
            "bpm": event.bpm,
            "created_at": event.sent_at.isoformat(),
            "response_status": "已回应" if response else "未回应"
        })
    
    return {"moments": moments}

@app.get("/api/relationship/{user_id}")
def get_relationship(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    rel = db.query(Relationship).filter(
        (Relationship.user_a_id == user_id) | 
        (Relationship.user_b_id == user_id),
        Relationship.status == "active"
    ).first()
    
    if not rel:
        return {"status": "unbound"}
    
    partner_id = rel.user_b_id if rel.user_a_id == user_id else rel.user_a_id
    return {
        "status": "bound",
        "partner_id": partner_id,
        "invite_code": rel.invite_code,
        "bind_time": rel.bind_time
    }

@app.post("/api/relationship/create")
def create_relationship(
    user_a_id: str,
    user_b_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_a_id)
    if user_a_id == user_b_id:
        raise HTTPException(status_code=422, detail="不能与自己绑定")
    if not db.query(User).filter(User.id == user_b_id).first():
        raise HTTPException(status_code=404, detail="接收方用户不存在")
    import random, string
    invite_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    rel = Relationship(
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        invite_code=invite_code
    )
    db.add(rel)
    db.commit()
    
    return {"invite_code": invite_code, "status": "created"}

@app.post("/webhook/tuya/event")
def handle_tuya_event(req: TuyaWebhookRequest, db: Session = Depends(get_db)):
    device = db.query(Device).filter(Device.device_id == req.device_id).first()
    if not device:
        return {"code": 404, "msg": "设备未绑定"}
    
    if req.dp_id == 104:
        latest_event = db.query(HeartbeatEvent).filter(
            HeartbeatEvent.receiver_id == device.user_id,
            HeartbeatEvent.status.in_(["delivered", "played", "acknowledged"])
        ).order_by(HeartbeatEvent.sent_at.desc()).first()
        
        if latest_event:
            response = Response(
                event_id=latest_event.event_id,
                from_user=device.user_id,
                response_type="touch" if req.value == 2 else "tap"
            )
            db.add(response)
            latest_event.status = "replied"
            db.commit()
            return {"code": 0, "msg": "已记录回应"}
    
    return {"code": 0, "msg": "收到"}

@app.post("/api/voice/upload")
async def upload_voice(
    user_id: str,
    duration: int,
    file: UploadFile = File(...),
    source: str = "watch",
    consent: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    if duration <= 0:
        raise HTTPException(status_code=422, detail="duration must be positive")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_VOICE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="only m4a, wav, mp3, and aac files are supported")

    content = await file.read(Config.MAX_VOICE_UPLOAD_BYTES + 1)
    if len(content) > Config.MAX_VOICE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="voice file is too large")

    VOICE_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid.uuid4()}{suffix}"
    file_path = VOICE_STORAGE_ROOT / stored_filename
    file_path.write_bytes(content)
    
    voice = VoiceRecord(
        user_id=user_id,
        file_url=stored_filename,
        duration=duration
    )
    db.add(voice)
    db.commit()

    pendant_filename = f"{uuid.uuid4()}.mp3"
    pendant_path = PENDANT_AUDIO_ROOT / pendant_filename
    pendant_ready, pendant_error = await run_in_threadpool(
        _transcode_for_pendant,
        file_path,
        pendant_path,
    )
    if pendant_ready:
        voice.pendant_file_url = pendant_filename
        voice.pendant_audio_status = "ready"
        voice.pendant_audio_error = None
        from datetime import datetime
        voice.pendant_audio_ready_at = datetime.utcnow()
    else:
        voice.pendant_audio_status = "unavailable"
        voice.pendant_audio_error = pendant_error
        if pendant_path.is_file():
            pendant_path.unlink()

    transcription = await run_in_threadpool(
        transcribe_event,
        file_path,
        voice.id,
        source,
        consent,
        "zh-CN",
    )
    voice.transcript = transcription.get("transcript")
    voice.transcription_status = transcription.get("status", "failed")
    voice.transcription_error = transcription.get("error_message")
    voice.transcription_provider = transcription.get("provider")
    voice.transcription_request_id = transcription.get("request_id")
    if voice.transcription_status == "completed":
        from datetime import datetime
        voice.transcribed_at = datetime.utcnow()
    db.commit()
    
    return {
        "voice_id": voice.id,
        "status": "uploaded",
        "ai_status": "pending",
        "transcription_status": voice.transcription_status,
        "transcript": voice.transcript,
        "transcription_error": voice.transcription_error,
        "transcription_request_id": voice.transcription_request_id,
        "pendant_audio_status": voice.pendant_audio_status,
    }


def get_voice_for_owner(voice_id: str, user_id: str, db: Session) -> VoiceRecord:
    voice = db.query(VoiceRecord).filter(VoiceRecord.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if voice.user_id != user_id:
        raise HTTPException(status_code=403, detail="voice does not belong to this user")
    return voice


@app.get("/api/voice/{voice_id}")
def download_voice(
    voice_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    voice = get_voice_for_owner(voice_id, user_id, db)
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="voice file not found")
    return FileResponse(file_path, media_type="application/octet-stream", filename=file_path.name)


@app.delete("/api/voice/{voice_id}")
def delete_voice(
    voice_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    voice = get_voice_for_owner(voice_id, user_id, db)
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT in file_path.parents and file_path.is_file():
        file_path.unlink()
    if voice.pendant_file_url:
        pendant_path = (PENDANT_AUDIO_ROOT / voice.pendant_file_url).resolve()
        if PENDANT_AUDIO_ROOT in pendant_path.parents and pendant_path.is_file():
            pendant_path.unlink()
    db.delete(voice)
    db.commit()
    return {"status": "deleted", "voice_id": voice_id}


def _transcribe_voice_file(file_path: Path, voice_id: str, source: str, consent: bool) -> dict:
    return transcribe_event(file_path, voice_id, source, consent, "zh-CN")


async def _transcribe_voice(voice: VoiceRecord, source: str, consent: bool, db: Session) -> dict:
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="voice file not found")
    voice.transcription_status = "processing"
    voice.transcription_error = None
    db.commit()
    result = await run_in_threadpool(_transcribe_voice_file, file_path, voice.id, source, consent)
    voice.transcript = result.get("transcript")
    voice.transcription_status = result.get("status", "failed")
    voice.transcription_error = result.get("error_message")
    voice.transcription_provider = result.get("provider")
    voice.transcription_request_id = result.get("request_id")
    if voice.transcription_status == "completed":
        from datetime import datetime
        voice.transcribed_at = datetime.utcnow()
    db.commit()
    return result


@app.post("/api/voice/{voice_id}/transcribe")
async def transcribe_voice(
    voice_id: str,
    user_id: str,
    source: str = "watch",
    consent: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    voice = get_voice_for_owner(voice_id, user_id, db)
    result = await _transcribe_voice(voice, source, consent, db)
    return {"voice_id": voice_id, **result}


@app.post("/api/voice/{voice_id}/transcript/confirm")
def confirm_transcript(
    voice_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    voice = get_voice_for_owner(voice_id, user_id, db)
    if voice.transcription_status != "completed" or not voice.transcript:
        raise HTTPException(status_code=409, detail="transcript is not ready for confirmation")
    voice.transcription_status = "confirmed"
    db.commit()
    return {"voice_id": voice_id, "status": "confirmed", "transcript": voice.transcript}

@app.post("/api/dnd/set")
def set_dnd(
    user_id: str,
    enabled: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    setting = db.query(DoNotDisturbSetting).filter(DoNotDisturbSetting.user_id == user_id).first()
    if setting:
        setting.enabled = enabled
    else:
        db.add(DoNotDisturbSetting(user_id=user_id, enabled=enabled))
    db.commit()
    return {"status": "ok", "dnd_enabled": enabled}

@app.get("/api/dnd/status")
def get_dnd(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    setting = db.query(DoNotDisturbSetting).filter(DoNotDisturbSetting.user_id == user_id).first()
    return {"dnd_enabled": setting.enabled if setting else False}

@app.post("/api/relationships/unbind")
def unbind_relationship(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_user_id(current_user, user_id)
    rel = db.query(Relationship).filter(
        (Relationship.user_a_id == user_id) | 
        (Relationship.user_b_id == user_id)
    ).first()
    
    if rel:
        rel.status = "unbound"
        db.commit()
        return {"status": "unbound"}
    
    return {"status": "not_found"}

# ========== 生活瞬间（Moments）接口 ==========

from pydantic import BaseModel
from typing import Optional

# 在文件顶部（schemas.py 里已经有类似的，但为了独立，先在这里定义一个）
class CreateMomentRequest(BaseModel):
    user_id: str
    title: str
    summary: str
    voice_id: Optional[str] = None


class GenerateMomentRequest(BaseModel):
    user_id: str
    content: Optional[str] = None
    voice_id: Optional[str] = None
    bpm: Optional[int] = None


@app.post("/api/moments/generate", response_model=CommonResponse)
def generate_moment(
    req: GenerateMomentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate and save a diary-style moment from user-approved content."""
    require_user_id(current_user, req.user_id)
    voice = None
    if req.voice_id:
        voice = get_voice_for_owner(req.voice_id, req.user_id, db)
        if voice.transcription_status != "confirmed" or not voice.transcript:
            raise HTTPException(status_code=409, detail="voice transcript must be confirmed before AI generation")
        content = voice.transcript.strip()
    else:
        content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=422, detail="content must not be empty")
    if len(content) > 10_000:
        raise HTTPException(status_code=413, detail="content is too long")
    if req.bpm is not None and not 30 <= req.bpm <= 240:
        raise HTTPException(status_code=422, detail="bpm must be between 30 and 240")

    try:
        diary = generate_diary(content, req.bpm)
    except AIServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    moment = Moment(
        user_id=req.user_id,
        title=diary["title"],
        summary=diary["summary"],
        raw_text=content,
        voice_id=voice.id if voice else req.voice_id,
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)

    return CommonResponse(
        code=0,
        msg="AI日记已生成",
        data={
            "id": moment.id,
            "user_id": moment.user_id,
            "title": moment.title,
            "summary": moment.summary,
            "raw_text": moment.raw_text,
            "voice_id": moment.voice_id,
            "created_at": moment.created_at.isoformat(),
            "ai_status": diary["ai_status"],
        },
    )


@app.post("/api/moments", response_model=CommonResponse)
def create_moment(
    req: CreateMomentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建一个生活瞬间
    请求体 JSON 格式：
    {
        "user_id": "user_001",
        "title": "标题",
        "summary": "摘要",
        "voice_id": "可选"
    }
    """
    require_user_id(current_user, req.user_id)
    moment = Moment(
        user_id=req.user_id,
        title=req.title,
        summary=req.summary,
        raw_text=req.summary,
        voice_id=req.voice_id
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)
    
    return CommonResponse(
        code=0,
        msg="创建成功",
        data={
            "id": moment.id,
            "title": moment.title,
            "summary": moment.summary,
            "created_at": moment.created_at.isoformat()
        }
    )
# 2. 查询单条生活瞬间
@app.get("/api/moments/{moment_id}", response_model=CommonResponse)
def get_moment(
    moment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """根据ID查询一条生活瞬间的完整信息"""
    moment = db.query(Moment).filter(Moment.id == moment_id).first()
    
    if not moment:
        return CommonResponse(code=404, msg="生活瞬间不存在")
    require_user_id(current_user, moment.user_id)
    
    return CommonResponse(
        code=0,
        msg="success",
        data={
            "id": moment.id,
            "user_id": moment.user_id,
            "title": moment.title,
            "summary": moment.summary,
            "raw_text": moment.raw_text,
            "voice_id": moment.voice_id,
            "created_at": moment.created_at.isoformat()
        }
    )


# 3. 查询用户的所有生活瞬间（分页）
@app.get("/api/moments", response_model=CommonResponse)
def get_moments_by_user(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    查询某个用户未归档的生活瞬间，按时间倒序
    - user_id: 用户ID
    - limit: 返回条数（默认20）
    - offset: 偏移量（用于分页）
    """
    require_user_id(current_user, user_id)
    # Archived diary entries remain in the database for history/audit, but are
    # intentionally hidden from the normal diary list.
    visible_moments = db.query(Moment).filter(
        Moment.user_id == user_id,
        # Rows created before the status column existed may have NULL here;
        # keep those legacy diary entries visible instead of hiding them.
        or_(Moment.status.is_(None), Moment.status != "archived"),
    )

    moments = visible_moments.order_by(
        Moment.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    total = visible_moments.count()
    
    data = []
    for m in moments:
        data.append({
            "id": m.id,
            "title": m.title,
            "summary": m.summary,
            "voice_id": m.voice_id,
            "created_at": m.created_at.isoformat()
        })
    
    return CommonResponse(
        code=0,
        msg="success",
        data={
            "total": total,
            "moments": data
        }
    )


# 4. 更新生活瞬间的状态
@app.put("/api/moments/{moment_id}/status", response_model=CommonResponse)
def update_moment_status(
    moment_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新生活瞬间的状态
    - status: 可选值 "active", "shared", "responded", "archived"
    """
    allowed_statuses = {"active", "shared", "responded", "archived"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="invalid moment status")

    moment = db.query(Moment).filter(Moment.id == moment_id).first()
    
    if not moment:
        return CommonResponse(code=404, msg="生活瞬间不存在")
    require_user_id(current_user, moment.user_id)
    
    moment.status = status
    db.commit()
    
    return CommonResponse(
        code=0,
        msg="状态更新成功",
        data={"id": moment_id, "status": status}
    )


# 5. 删除生活瞬间（软删除，实际是标记为已归档）
@app.delete("/api/moments/{moment_id}", response_model=CommonResponse)
def delete_moment(
    moment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除生活瞬间（软删除，标记为 archived）"""
    moment = db.query(Moment).filter(Moment.id == moment_id).first()
    
    if not moment:
        return CommonResponse(code=404, msg="生活瞬间不存在")
    require_user_id(current_user, moment.user_id)
    
    moment.status = "archived"
    db.commit()
    
    return CommonResponse(code=0, msg="已归档")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
