"""Client for iFlytek's asynchronous recording-file transcription model.

The client follows the official two-step API: upload binary audio, then poll
``/v2/getResult`` until the order is complete. Credentials are read by the
caller and are never logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import string
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://office-api-ist-dx.iflyaisol.com"
TERMINAL_SUCCESS = 4
TERMINAL_FAILURE = -1


class IflytekError(RuntimeError):
    """Provider/API error with an optional provider error code."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


def build_signature(access_key_secret: str, params: Mapping[str, Any]) -> str:
    """Create the HMAC-SHA1/Base64 signature required by the official API."""
    parts = []
    for key in sorted(params):
        if key == "signature":
            continue
        value = params[key]
        if value is None or value == "":
            continue
        # The Java example in the official document sorts keys naturally and
        # applies application/x-www-form-urlencoded escaping to values.
        parts.append(f"{key}={quote_plus(str(value), encoding='utf-8')}")
    base_string = "&".join(parts).encode("utf-8")
    digest = hmac.new(access_key_secret.encode("utf-8"), base_string, hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")


def _random16() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IflytekError("讯飞接口返回了无效 JSON") from exc
    if not isinstance(data, dict):
        raise IflytekError("讯飞接口返回格式不是 JSON 对象")
    return data


def parse_order_result(order_result: Any) -> str:
    """Flatten the documented lattice/json_1best structure into plain text."""
    if not order_result:
        return ""
    value = order_result
    for _ in range(3):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value.strip()
        else:
            break
    if not isinstance(value, dict):
        return ""
    words: list[str] = []
    for lattice_item in value.get("lattice", []):
        if not isinstance(lattice_item, dict):
            continue
        best = lattice_item.get("json_1best", "")
        try:
            best_obj = json.loads(best) if isinstance(best, str) else best
        except json.JSONDecodeError:
            continue
        st = best_obj.get("st", {}) if isinstance(best_obj, dict) else {}
        for rt_item in st.get("rt", []):
            for ws_item in (rt_item or {}).get("ws", []):
                for candidate in (ws_item or {}).get("cw", []):
                    if isinstance(candidate, dict):
                        word = str(candidate.get("w", "")).strip()
                        if word:
                            words.append(word)
                    break  # first candidate is the 1-best result
    return "".join(words).strip()


class IflytekFileASR:
    def __init__(
        self,
        app_id: str,
        api_key: str,
        api_secret: str,
        base_url: str = DEFAULT_BASE_URL,
        language: str = "autodialect",
        timeout: float = 30.0,
        poll_interval: float = 2.0,
        max_polls: int = 90,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.language = language if language in {"autodialect", "autominor"} else "autodialect"
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls
        self.opener = opener

    def _request(self, path: str, params: Mapping[str, Any], body: bytes, content_type: str) -> dict[str, Any]:
        signature = build_signature(self.api_secret, params)
        query = urlencode(dict(params), doseq=False, quote_via=quote_plus)
        request = Request(
            f"{self.base_url}{path}?{query}",
            data=body,
            headers={"Content-Type": content_type, "signature": signature},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                data = _json_response(response)
        except IflytekError:
            raise
        except Exception as exc:
            raise IflytekError(f"请求讯飞接口失败: {exc}") from exc
        code = str(data.get("code", ""))
        if code != "000000":
            raise IflytekError(str(data.get("descInfo", "讯飞接口返回错误")), code=code)
        return data

    def transcribe(self, audio_path: Path) -> str:
        payload = audio_path.read_bytes()
        if not payload:
            raise ValueError("音频文件为空")
        random_value = _random16()
        upload_params = {
            "appId": self.app_id,
            "accessKeyId": self.api_key,
            "dateTime": _now(),
            "signatureRandom": random_value,
            "fileSize": str(len(payload)),
            "fileName": audio_path.name,
            "durationCheckDisable": "true",
            "language": self.language,
        }
        uploaded = self._request("/v2/upload", upload_params, payload, "application/octet-stream")
        order_id = ((uploaded.get("content") or {}).get("orderId"))
        if not order_id:
            raise IflytekError("上传成功但未返回 orderId")
        for attempt in range(self.max_polls):
            if attempt:
                time.sleep(self.poll_interval)
            result_params = {
                "accessKeyId": self.api_key,
                "dateTime": _now(),
                "signatureRandom": random_value,
                "orderId": order_id,
                "resultType": "transfer",
            }
            result = self._request("/v2/getResult", result_params, b"{}", "application/json")
            content = result.get("content") or {}
            order_info = content.get("orderInfo") or {}
            status = int(order_info.get("status", 3))
            if status == TERMINAL_SUCCESS:
                text = parse_order_result(content.get("orderResult"))
                if not text:
                    raise IflytekError("转写完成但结果为空", code="EMPTY_RESULT")
                return text
            if status == TERMINAL_FAILURE:
                raise IflytekError("讯飞转写订单失败", code=str(order_info.get("failType", status)))
        raise TimeoutError("等待讯飞转写结果超时")
