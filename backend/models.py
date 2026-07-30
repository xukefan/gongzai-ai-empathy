from sqlalchemy import Column, String, Integer, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.sql import func
from database import Base
import uuid

def gen_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(50), unique=True, nullable=False)
    phone = Column(String(20), unique=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Relationship(Base):
    __tablename__ = "relationships"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_a_id = Column(String(36), nullable=False)
    user_b_id = Column(String(36), nullable=False)
    invite_code = Column(String(10), unique=True, nullable=False)
    status = Column(String(20), default="active")
    bind_time = Column(DateTime, server_default=func.now())

class Device(Base):
    __tablename__ = "devices"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), nullable=False)
    device_id = Column(String(50), unique=True, nullable=False)
    product_id = Column(String(50), nullable=False)
    bind_time = Column(DateTime, server_default=func.now())

class HeartbeatEvent(Base):
    __tablename__ = "heartbeat_events"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    event_id = Column(String(36), unique=True, nullable=False, default=gen_uuid)
    sender_id = Column(String(36), nullable=False)
    receiver_id = Column(String(36), nullable=False)
    bpm = Column(Integer, nullable=False)
    pattern = Column(String(200))
    sent_at = Column(DateTime, server_default=func.now())
    status = Column(String(20), default="created")  # created/uploaded/delivered/played/acknowledged/replied/failed
    
class VoiceRecord(Base):
    __tablename__ = "voice_records"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), nullable=False)
    file_url = Column(String(500), nullable=False)
    duration = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())

class Moment(Base):
    __tablename__ = "moments"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), nullable=False)
    title = Column(String(100))
    summary = Column(Text)
    raw_text = Column(Text)
    voice_id = Column(String(36), ForeignKey("voice_records.id"))
    status = Column(String(20), default="active")  # active/shared/responded/archived  ← 新增这一行
    created_at = Column(DateTime, server_default=func.now())

class Response(Base):
    __tablename__ = "responses"
    id = Column(String(36), primary_key=True, default=gen_uuid)
    event_id = Column(String(36), nullable=False)
    from_user = Column(String(36), nullable=False)
    response_type = Column(String(20), default="touch")
    created_at = Column(DateTime, server_default=func.now())