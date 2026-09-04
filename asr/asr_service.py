"""Unified ASR response wrapper for the member-2 integration contract."""

import argparse
import json
import time
import uuid
from pathlib import Path

try:
    from .iflytek_file_asr import IflytekFileASR
except ImportError:  # supports ``python ai/asr_service.py`` from repository root
    from iflytek_file_asr import IflytekFileASR


def _client() -> IflytekFileASR:
    import os

    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).with_name(".env"))
    except ImportError:
        # Environment variables can still be supplied by the shell.
        pass

    values = {name: os.getenv(name, "") for name in ("IFLYTEK_APP_ID", "IFLYTEK_API_KEY", "IFLYTEK_API_SECRET")}
    if not all(values.values()):
        raise RuntimeError("未配置 IFLYTEK_APP_ID/API_KEY/API_SECRET")
    return IflytekFileASR(
        **{k.removeprefix("IFLYTEK_").lower().replace("api_", "api_"): v for k, v in values.items()},
        base_url=os.getenv("IFLYTEK_BASE_URL", "https://office-api-ist-dx.iflyaisol.com"),
        language=os.getenv("IFLYTEK_LANGUAGE", "autodialect"),
    )


def transcribe_event(
    audio_path: Path,
    event_id: str,
    source: str,
    consent: bool,
    language: str = "zh-CN",
) -> dict:
    request_id = str(uuid.uuid4())
    started = time.monotonic()
    base = {
        "request_id": request_id,
        "event_id": event_id,
        "language": language,
        "provider": "iflytek",
        "duration_ms": None,
        "error_code": None,
        "error_message": None,
        "schema_version": 1,
    }
    if source not in {"watch", "pendant"}:
        return {**base, "status": "failed", "transcript": None,
                "error_code": "INVALID_REQUEST", "error_message": "source 必须是 watch 或 pendant"}
    if not consent:
        return {**base, "status": "unauthorized", "transcript": None,
                "error_code": "NO_CONSENT", "error_message": "用户未授权语音转写"}
    if not audio_path.exists() or audio_path.stat().st_size == 0:
        return {**base, "status": "invalid_audio", "transcript": None,
                "error_code": "EMPTY_AUDIO", "error_message": "音频文件不存在或为空"}
    try:
        transcript = _client().transcribe(audio_path)
    except TimeoutError as exc:
        return {**base, "status": "failed", "transcript": None,
                "error_code": "ASR_TIMEOUT", "error_message": str(exc)}
    except ValueError as exc:
        return {**base, "status": "invalid_audio", "transcript": None,
                "error_code": "INVALID_FORMAT", "error_message": str(exc)}
    except Exception as exc:  # provider-specific error is surfaced to caller
        return {**base, "status": "failed", "transcript": None,
                "error_code": "ASR_PROVIDER_ERROR", "error_message": str(exc)}
    if not transcript:
        return {**base, "status": "empty_transcript", "transcript": None,
                "error_code": "EMPTY_AUDIO", "error_message": "未识别到有效文字"}
    return {**base, "status": "completed", "transcript": transcript,
            "duration_ms": round((time.monotonic() - started) * 1000)}


def main() -> None:
    parser = argparse.ArgumentParser(description="输出统一 ASR JSON")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--event-id", required=True)
    parser.add_argument("--source", choices=["watch", "pendant"], required=True)
    parser.add_argument("--consent", action="store_true")
    args = parser.parse_args()
    print(json.dumps(transcribe_event(
        args.audio, args.event_id, args.source, args.consent
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
