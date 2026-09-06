"""Small server-side AI adapter used to turn shared moments into diary entries.

The adapter speaks the OpenAI-compatible Chat Completions protocol so the
deployment can use the team's chosen model provider without putting an API key
in the iPhone app.  When no key is configured, it returns a clearly marked
fallback entry so the rest of the product can still be tested end to end.
"""

import json
import re
from typing import Any, Optional

from config import Config
from ai_prompts import MOMENT_SYSTEM_PROMPT, PROMPT_VERSION, build_moment_messages
from ai_errors import AIServiceError
from deepseek_client import chat_completion


SCHEMA_VERSION = 1
MAX_TAGS = 5
MAX_REPLIES = 3
HIGH_RISK_TERMS = (
    "自杀", "自残", "轻生", "不想活", "杀了", "伤害自己", "呼吸困难", "胸痛",
)


def _safety_flags(content: str) -> list[str]:
    """Flag explicit high-risk wording without making a diagnosis."""
    flags: list[str] = []
    if any(term in content for term in HIGH_RISK_TERMS):
        flags.append("high_risk_content_review")
    return flags


def _fallback_entry(content: str, bpm: Optional[int]) -> dict:
    first_line = next(
        (line.strip() for line in content.splitlines() if line.strip()),
        "生活片段",
    )
    title = first_line[:28]
    if len(first_line) > 28:
        title += "…"
    summary = content.strip()[:160]
    if bpm is not None:
        summary = f"{summary}（分享时心率约 {bpm} BPM）"
    return {
        "title": title or "生活片段",
        "summary": summary or "记录了一个生活瞬间。",
        "tags": ["生活片段"],
        "suggested_replies": [],
        "safety_flags": _safety_flags(content),
        "ai_status": "fallback",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": Config.AI_PROMPT_VERSION or PROMPT_VERSION,
    }


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise AIServiceError("AI返回的内容不是有效JSON") from exc
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as nested_exc:
            raise AIServiceError("AI返回的内容不是有效JSON") from nested_exc

    if not isinstance(parsed, dict):
        raise AIServiceError("AI返回的数据结构无效")
    title = str(parsed.get("title", "")).strip()
    summary = str(parsed.get("summary", "")).strip()
    if not title or not summary:
        raise AIServiceError("AI返回的日记缺少标题或摘要")

    raw_tags = parsed.get("tags", [])
    raw_replies = parsed.get("suggested_replies", [])
    raw_flags = parsed.get("safety_flags", [])
    if not isinstance(raw_tags, list) or not isinstance(raw_replies, list) or not isinstance(raw_flags, list):
        raise AIServiceError("AI返回的结构化字段类型无效")

    tags = [str(item).strip() for item in raw_tags if str(item).strip()][:MAX_TAGS]
    replies = [str(item).strip() for item in raw_replies if str(item).strip()][:MAX_REPLIES]
    flags = [str(item).strip() for item in raw_flags if str(item).strip()]
    return {
        "title": title[:100],
        "summary": summary[:2000],
        "tags": tags,
        "suggested_replies": replies,
        "safety_flags": flags,
        "ai_status": "generated",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": Config.AI_PROMPT_VERSION or PROMPT_VERSION,
    }


def _apply_safety_policy(entry: dict[str, Any], content: str) -> dict[str, Any]:
    """Enforce local high-risk handling instead of trusting model output alone."""
    local_flags = _safety_flags(content)
    flags = list(dict.fromkeys([*entry["safety_flags"], *local_flags]))
    entry["safety_flags"] = flags
    if "high_risk_content_review" in flags:
        # Reply drafts are optional and must not be offered for high-risk content.
        entry["suggested_replies"] = []
    return entry


def _request_model(endpoint: str, headers: dict[str, str], payload: dict[str, Any]) -> str:
    # Keep this function as a patchable seam for unit tests and provider swaps.
    # DeepSeek uses the same Chat Completions request shape.
    del endpoint, headers
    return chat_completion(payload["messages"], model=payload.get("model"))


def generate_diary(content: str, bpm: Optional[int] = None) -> dict:
    """Generate a faithful diary title and summary from user-approved text."""

    normalized = content.strip()
    if not normalized:
        raise AIServiceError("content must not be empty")

    if not Config.AI_API_KEY:
        return _fallback_entry(normalized, bpm)

    endpoint = Config.AI_API_BASE_URL.rstrip("/")
    if not endpoint.endswith("/chat/completions"):
        endpoint += "/chat/completions"

    messages = build_moment_messages(normalized, bpm)
    system_prompt = MOMENT_SYSTEM_PROMPT
    payload = {
        "model": Config.AI_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {Config.AI_API_KEY}",
        "Content-Type": "application/json",
    }

    text = _request_model(endpoint, headers, payload)
    try:
        return _apply_safety_policy(_extract_json(text), normalized)
    except AIServiceError as first_error:
        # One repair attempt keeps malformed model output visible without looping.
        repair_payload = {
            **payload,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"原始内容：{normalized}\n请重新输出合法JSON。上一次输出无效，"
                        "只返回对象，不要Markdown代码块。"
                    ),
                },
            ],
        }
        try:
            repaired = _request_model(endpoint, headers, repair_payload)
            return _apply_safety_policy(_extract_json(repaired), normalized)
        except AIServiceError as second_error:
            raise AIServiceError(f"AI结构化输出校验失败（已重试一次）: {second_error}") from first_error
