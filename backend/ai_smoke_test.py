"""One-record DeepSeek smoke test using synthetic text only.

This command never reads an audio file and prints no API key. Run it only after
AI_API_KEY is configured in the local/production environment.
"""

import argparse
import json

from ai_service import AIServiceError, generate_diary


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test DeepSeek AI moment generation")
    parser.add_argument("--text", default="今天完成了一个脱敏测试记录。")
    parser.add_argument("--bpm", type=int, default=None)
    args = parser.parse_args()
    try:
        result = generate_diary(args.text, args.bpm)
    except AIServiceError as exc:
        print(json.dumps({"code": exc.code, "retryable": exc.retryable, "message": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ai_status") == "generated" else 2


if __name__ == "__main__":
    raise SystemExit(main())
