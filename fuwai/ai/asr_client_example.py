"""成员 2 调用 ASR HTTPS 接口的最小示例。

安装 requests 后运行：
    python ai/asr_client_example.py record.wav event_001 watch
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import requests


def transcribe(
    audio_path: str | Path,
    event_id: str,
    source: str,
    base_url: str,
    api_key: str,
    timeout: float = 240.0,
) -> dict:
    path = Path(audio_path)
    with path.open("rb") as audio:
        response = requests.post(
            f"{base_url.rstrip('/')}/internal/ai/asr",
            headers={"X-API-Key": api_key},
            files={"file": (path.name, audio, "application/octet-stream")},
            data={
                "event_id": event_id,
                "source": source,
                "consent": "true",
                "language": "zh-CN",
            },
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("用法: python ai/asr_client_example.py <音频文件> <event_id> <watch|pendant>")
    result = transcribe(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        os.environ["ASR_BASE_URL"],
        os.environ["ASR_INTERNAL_API_KEY"],
    )
    print(result)
