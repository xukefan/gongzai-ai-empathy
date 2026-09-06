from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List
import uuid
from pathlib import Path

from database import get_db, engine
from models import Base, User, Relationship, Device, HeartbeatEvent, VoiceRecord, Moment, Response, DoNotDisturbSetting
from schemas import *
from tuya_client import TuyaClient
from config import Config
from ai_service import AIServiceError, generate_diary

Base.metadata.create_all(bind=engine)

app = FastAPI(title="共感挂件后端API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

tuya = TuyaClient()
VOICE_STORAGE_ROOT = (Path(__file__).resolve().parent / Config.VOICE_STORAGE_DIR).resolve()
ALLOWED_VOICE_EXTENSIONS = {".m4a", ".wav", ".mp3", ".aac"}

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "coglink-backend"}

@app.post("/api/heartbeat/send", response_model=HeartbeatSendResponse)
def send_heartbeat(req: HeartbeatSendRequest, db: Session = Depends(get_db)):
    event_id = str(uuid.uuid4())
    
    event = HeartbeatEvent(
        event_id=event_id,
        sender_id=req.sender_id,
        receiver_id=req.receiver_id,
        bpm=req.bpm,
        pattern=req.pattern
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

@app.post("/api/devices/bind", response_model=DeviceBindResponse)
def bind_device(req: DeviceBindRequest, db: Session = Depends(get_db)):
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
def get_timeline(user_id: str, db: Session = Depends(get_db)):
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
def get_relationship(user_id: str, db: Session = Depends(get_db)):
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
def create_relationship(user_a_id: str, user_b_id: str, db: Session = Depends(get_db)):
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
    db: Session = Depends(get_db)
):
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
    
    return {
        "voice_id": voice.id,
        "status": "uploaded",
        "ai_status": "pending"
    }


def get_voice_for_owner(voice_id: str, user_id: str, db: Session) -> VoiceRecord:
    voice = db.query(VoiceRecord).filter(VoiceRecord.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="voice not found")
    if voice.user_id != user_id:
        raise HTTPException(status_code=403, detail="voice does not belong to this user")
    return voice


@app.get("/api/voice/{voice_id}")
def download_voice(voice_id: str, user_id: str, db: Session = Depends(get_db)):
    voice = get_voice_for_owner(voice_id, user_id, db)
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT not in file_path.parents or not file_path.is_file():
        raise HTTPException(status_code=404, detail="voice file not found")
    return FileResponse(file_path, media_type="application/octet-stream", filename=file_path.name)


@app.delete("/api/voice/{voice_id}")
def delete_voice(voice_id: str, user_id: str, db: Session = Depends(get_db)):
    voice = get_voice_for_owner(voice_id, user_id, db)
    file_path = (VOICE_STORAGE_ROOT / voice.file_url).resolve()
    if VOICE_STORAGE_ROOT in file_path.parents and file_path.is_file():
        file_path.unlink()
    db.delete(voice)
    db.commit()
    return {"status": "deleted", "voice_id": voice_id}

@app.post("/api/dnd/set")
def set_dnd(user_id: str, enabled: bool, db: Session = Depends(get_db)):
    setting = db.query(DoNotDisturbSetting).filter(DoNotDisturbSetting.user_id == user_id).first()
    if setting:
        setting.enabled = enabled
    else:
        db.add(DoNotDisturbSetting(user_id=user_id, enabled=enabled))
    db.commit()
    return {"status": "ok", "dnd_enabled": enabled}

@app.get("/api/dnd/status")
def get_dnd(user_id: str, db: Session = Depends(get_db)):
    setting = db.query(DoNotDisturbSetting).filter(DoNotDisturbSetting.user_id == user_id).first()
    return {"dnd_enabled": setting.enabled if setting else False}

@app.post("/api/relationships/unbind")
def unbind_relationship(user_id: str, db: Session = Depends(get_db)):
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
    content: str
    voice_id: Optional[str] = None
    bpm: Optional[int] = None


@app.post("/api/moments/generate", response_model=CommonResponse)
def generate_moment(req: GenerateMomentRequest, db: Session = Depends(get_db)):
    """Generate and save a diary-style moment from user-approved content."""
    content = req.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="content must not be empty")
    if len(content) > 10_000:
        raise HTTPException(status_code=413, detail="content is too long")
    if req.bpm is not None and not 30 <= req.bpm <= 240:
        raise HTTPException(status_code=422, detail="bpm must be between 30 and 240")

    try:
        diary = generate_diary(content, req.bpm)
    except AIServiceError as exc:
        status_code = 504 if exc.code == "AI_TIMEOUT" else 502
        raise HTTPException(
            status_code=status_code,
            detail={
                "code": exc.code,
                "message": str(exc),
                "retryable": exc.retryable,
                "schema_version": 1,
            },
        ) from exc

    moment = Moment(
        user_id=req.user_id,
        title=diary["title"],
        summary=diary["summary"],
        raw_text=content,
        voice_id=req.voice_id,
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
            "tags": diary.get("tags", []),
            "suggested_replies": diary.get("suggested_replies", []),
            "safety_flags": diary.get("safety_flags", []),
            "schema_version": diary.get("schema_version", 1),
            "prompt_version": diary.get("prompt_version", "moment-v1"),
        },
    )


@app.post("/api/moments", response_model=CommonResponse)
def create_moment(req: CreateMomentRequest, db: Session = Depends(get_db)):
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
def get_moment(moment_id: str, db: Session = Depends(get_db)):
    """根据ID查询一条生活瞬间的完整信息"""
    moment = db.query(Moment).filter(Moment.id == moment_id).first()
    
    if not moment:
        return CommonResponse(code=404, msg="生活瞬间不存在")
    
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
    db: Session = Depends(get_db)
):
    """
    查询某个用户的所有生活瞬间，按时间倒序
    - user_id: 用户ID
    - limit: 返回条数（默认20）
    - offset: 偏移量（用于分页）
    """
    moments = db.query(Moment).filter(
        Moment.user_id == user_id
    ).order_by(
        Moment.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    total = db.query(Moment).filter(Moment.user_id == user_id).count()
    
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
    db: Session = Depends(get_db)
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
    
    moment.status = status
    db.commit()
    
    return CommonResponse(
        code=0,
        msg="状态更新成功",
        data={"id": moment_id, "status": status}
    )


# 5. 删除生活瞬间（软删除，实际是标记为已归档）
@app.delete("/api/moments/{moment_id}", response_model=CommonResponse)
def delete_moment(moment_id: str, db: Session = Depends(get_db)):
    """删除生活瞬间（软删除，标记为 archived）"""
    moment = db.query(Moment).filter(Moment.id == moment_id).first()
    
    if not moment:
        return CommonResponse(code=404, msg="生活瞬间不存在")
    
    moment.status = "archived"
    db.commit()
    
    return CommonResponse(code=0, msg="已归档")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
