import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./coglink.db")

    # Keep credentials outside source control. Set these in the deployment environment.
    TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
    TUYA_ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
    TUYA_API_ENDPOINT = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyacn.com")

    # These must match the function codes defined in the Tuya product schema.
    TUYA_BPM_CODE = os.getenv("TUYA_BPM_CODE", "bpm")
    TUYA_PATTERN_CODE = os.getenv("TUYA_PATTERN_CODE", "pattern")
    TUYA_TRIGGER_CODE = os.getenv("TUYA_TRIGGER_CODE", "trigger")

    VOICE_STORAGE_DIR = os.getenv("VOICE_STORAGE_DIR", "uploads/voices")
    MAX_VOICE_UPLOAD_BYTES = int(os.getenv("MAX_VOICE_UPLOAD_BYTES", 20 * 1024 * 1024))
    ASR_INTERNAL_API_KEY = os.getenv("ASR_INTERNAL_API_KEY")
    ASR_MAX_AUDIO_BYTES = int(os.getenv("ASR_MAX_AUDIO_BYTES", 500 * 1024 * 1024))
    ASR_LANGUAGE = os.getenv("IFLYTEK_LANGUAGE", "autodialect")
    AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
    AI_API_KEY = os.getenv("AI_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", 30))
    CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
