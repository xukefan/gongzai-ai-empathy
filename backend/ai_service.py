"""Small server-side AI adapter used to turn shared moments into diary entries.

The adapter speaks the OpenAI-compatible Chat Completions protocol so the
deployment can use the team's chosen model provider without putting an API key
in the iPhone app.  When no key is configured, it returns a clearly marked
fallback entry so the rest of the product can still be tested end to end.
"""

import json
import re
from typing import Optional

import requests

from config import Config


class AIServiceError(RuntimeError):
    """Raised when the configured AI provider cannot generate an entry."""


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
        "ai_status": "fallback",
    }


def _extract_json(text: str) -> dict:
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
    return {
        "title": title[:100],
        "summary": summary[:2000],
        "ai_status": "generated",
    }


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

    context = normalized
    if bpm is not None:
        context += f"\n[仅作为背景信息] 分享时心率约为 {bpm} BPM。不要据此诊断情绪。"

    payload = {
        "model": Config.AI_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是生活日记整理助手。只根据用户提供的原话生成一条简短、"
                    "忠实、不夸大的中文日记。不要补写未发生的事实，不要进行心理或"
                    "医疗诊断。只输出JSON对象，字段必须是 title 和 summary。"
                ),
            },
            {
                "role": "user",
                "content": context,
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {Config.AI_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=Config.AI_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        text = body["choices"][0]["message"]["content"]
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIServiceError(f"AI服务调用失败: {exc}") from exc

    return _extract_json(text)
