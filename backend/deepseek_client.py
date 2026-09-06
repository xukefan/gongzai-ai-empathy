"""Minimal OpenAI-compatible DeepSeek client used by the AI service."""

from typing import Any

import requests

from ai_errors import AIServiceError
from config import Config


def chat_completion(messages: list[dict[str, str]], *, model: str | None = None) -> str:
    """Call DeepSeek and return only the assistant message content.

    The API key remains server-side. The client deliberately does not log the
    request body, audio references, user text, or authorization header.
    """
    if not Config.AI_API_KEY:
        raise AIServiceError("AI_API_KEY 未配置", code="AI_PROVIDER_UNAVAILABLE", retryable=False)

    base_url = Config.AI_API_BASE_URL.rstrip("/")
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    payload: dict[str, Any] = {
        "model": model or Config.AI_MODEL,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "messages": messages,
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
        if response.status_code in (408, 409, 429) or response.status_code >= 500:
            raise AIServiceError(
                "DeepSeek 服务暂时不可用",
                code="AI_PROVIDER_UNAVAILABLE" if response.status_code != 408 else "AI_TIMEOUT",
                retryable=True,
            )
        if response.status_code in (401, 403):
            raise AIServiceError("DeepSeek 鉴权失败", code="AI_PROVIDER_AUTH_FAILED", retryable=False)
        if 400 <= response.status_code < 500:
            raise AIServiceError("DeepSeek 请求参数或模型配置无效", code="AI_INVALID_REQUEST", retryable=False)
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError("DeepSeek 返回内容为空", code="AI_INVALID_RESPONSE", retryable=True)
        return content
    except AIServiceError:
        raise
    except requests.Timeout as exc:
        raise AIServiceError("DeepSeek 请求超时", code="AI_TIMEOUT", retryable=True) from exc
    except requests.RequestException as exc:
        raise AIServiceError("DeepSeek 网络请求失败", code="AI_PROVIDER_UNAVAILABLE", retryable=True) from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AIServiceError("DeepSeek 响应结构无效", code="AI_INVALID_RESPONSE", retryable=True) from exc
