"""Authentication helpers for the Gongzai API.

The competition prototype uses short-lived HMAC-signed JWTs.  Passwords are
stored as salted PBKDF2 hashes, so neither passwords nor bearer tokens are
written to the repository or logs.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from config import Config
from database import get_db
from models import User


PBKDF2_ITERATIONS = 310_000


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, iterations_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = _b64decode(salt_text)
        expected = _b64decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(actual, expected)


def _signing_key() -> bytes:
    secret = Config.AUTH_SECRET_KEY
    if not secret or secret == "dev-only-change-this":
        # Keep local development convenient, but make an unsafe deployment
        # immediately visible rather than silently accepting a weak key.
        if Config.ENVIRONMENT == "production":
            raise RuntimeError("AUTH_SECRET_KEY must be set in production")
    return secret.encode("utf-8")


def create_access_token(user: User) -> tuple[str, int]:
    now = int(time.time())
    expires_at = now + Config.AUTH_TOKEN_TTL_SECONDS
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.id,
        "username": user.username,
        "iat": now,
        "exp": expires_at,
    }
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode())
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = _b64encode(hmac.new(_signing_key(), signing_input, hashlib.sha256).digest())
    return f"{encoded_header}.{encoded_payload}.{signature}", expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        encoded_header, encoded_payload, signature = token.split(".", 2)
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = _b64encode(
            hmac.new(_signing_key(), signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(encoded_payload))
        if int(payload.get("exp", 0)) <= int(time.time()):
            raise ValueError("token expired")
        if not payload.get("sub"):
            raise ValueError("token subject missing")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeError, binascii.Error):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="登录已失效，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="需要登录后访问",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(authorization.split(" ", 1)[1].strip())
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def require_user_id(current_user: User, requested_user_id: str) -> None:
    if current_user.id != requested_user_id:
        raise HTTPException(status_code=403, detail="无权访问其他用户的数据")
