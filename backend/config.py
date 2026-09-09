import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./coglink.db")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

    # User authentication.  Set a long random value in the server's private
    # .env; the development fallback is intentionally rejected in production.
    AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "dev-only-change-this")
    AUTH_TOKEN_TTL_SECONDS = max(
        300, min(int(os.getenv("AUTH_TOKEN_TTL_SECONDS", "604800")), 2_592_000)
    )

    # Keep credentials outside source control. Set these in the deployment environment.
    TUYA_ACCESS_ID = os.getenv("TUYA_ACCESS_ID")
    TUYA_ACCESS_SECRET = os.getenv("TUYA_ACCESS_SECRET")
    TUYA_API_ENDPOINT = os.getenv("TUYA_API_ENDPOINT", "https://openapi.tuyacn.com")

    # These must match the function codes defined in the Tuya product schema.
    TUYA_BPM_CODE = os.getenv("TUYA_BPM_CODE", "bpm")
    TUYA_PATTERN_CODE = os.getenv("TUYA_PATTERN_CODE", "pattern")
    TUYA_TRIGGER_CODE = os.getenv("TUYA_TRIGGER_CODE", "trigger")
    # direct: pendant polls FastAPI over Wi-Fi; tuya: legacy DP delivery.
    PENDANT_DELIVERY_MODE = os.getenv("PENDANT_DELIVERY_MODE", "direct").strip().lower()
    PENDANT_API_TOKEN = os.getenv("PENDANT_API_TOKEN")

    # The pendant receives an opaque, short-lived URL for a derived MP3.  This
    # is deliberately separate from PENDANT_API_TOKEN, which remains a header
    # used only for the pendant's event polling and acknowledgement APIs.
    PENDANT_PLAYBACK_TICKET_SECRET = os.getenv("PENDANT_PLAYBACK_TICKET_SECRET")
    PENDANT_PLAYBACK_TICKET_TTL_SECONDS = max(
        30, min(int(os.getenv("PENDANT_PLAYBACK_TICKET_TTL_SECONDS", "300")), 3600)
    )
    PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "").strip().rstrip("/")

    VOICE_STORAGE_DIR = os.getenv("VOICE_STORAGE_DIR", "uploads/voices")
    # Original recordings remain in VOICE_STORAGE_DIR for ASR and diary use.
    # A normalized, pendant-playable MP3 is written separately so the original
    # file is never overwritten or exposed to the pendant endpoint.
    PENDANT_AUDIO_DIR = os.getenv("PENDANT_AUDIO_DIR", "uploads/pendant_audio")
    FFMPEG_BINARY = os.getenv("FFMPEG_BINARY", "ffmpeg")
    PENDANT_AUDIO_SAMPLE_RATE = int(os.getenv("PENDANT_AUDIO_SAMPLE_RATE", "16000"))
    PENDANT_AUDIO_BITRATE = os.getenv("PENDANT_AUDIO_BITRATE", "32k")
    PENDANT_AUDIO_TRANSCODE_TIMEOUT_SECONDS = max(
        5, min(int(os.getenv("PENDANT_AUDIO_TRANSCODE_TIMEOUT_SECONDS", "30")), 120)
    )
    MAX_VOICE_UPLOAD_BYTES = int(os.getenv("MAX_VOICE_UPLOAD_BYTES", 20 * 1024 * 1024))
    ASR_INTERNAL_API_KEY = os.getenv("ASR_INTERNAL_API_KEY")
    ASR_MAX_AUDIO_BYTES = int(os.getenv("ASR_MAX_AUDIO_BYTES", 500 * 1024 * 1024))
    ASR_LANGUAGE = os.getenv("IFLYTEK_LANGUAGE", "autodialect")
    AI_API_BASE_URL = os.getenv("AI_API_BASE_URL", "https://api.openai.com/v1")
    AI_API_KEY = os.getenv("AI_API_KEY")
    AI_MODEL = os.getenv("AI_MODEL", "gpt-4o-mini")
    # Keep prompt/version metadata available to newer AI service modules.
    # An empty value lets the service fall back to its bundled prompt version.
    AI_PROMPT_VERSION = os.getenv("AI_PROMPT_VERSION", "")
    AI_TIMEOUT_SECONDS = int(os.getenv("AI_TIMEOUT_SECONDS", 30))
    # A short retry is enough for transient upstream 5xx/timeout failures.
    # The diary endpoint falls back to the approved original text if all
    # attempts fail, so an AI outage never blocks the user's record.
    AI_MAX_ATTEMPTS = max(1, min(int(os.getenv("AI_MAX_ATTEMPTS", "3")), 3))
    AI_RETRY_DELAY_SECONDS = max(
        0.0, min(float(os.getenv("AI_RETRY_DELAY_SECONDS", "0.8")), 5.0)
    )
    CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]

    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))
