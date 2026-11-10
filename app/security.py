"""Пароли, JWT-сессии и шифрование учётных данных интеграций."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from cryptography.fernet import Fernet, InvalidToken

from .config import SECRET_KEY, TOKEN_TTL_MINUTES

_PBKDF2_ROUNDS = 260_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ROUNDS)
    return "pbkdf2_sha256${}${}${}".format(
        _PBKDF2_ROUNDS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def create_token(user_id: int, organization_id: int | None, is_superadmin: bool) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "org": organization_id,
        "sa": bool(is_superadmin),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=TOKEN_TTL_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(("creds:" + SECRET_KEY).encode()).digest())
    return Fernet(key)


def encrypt_credentials(data: dict) -> str:
    import json

    if not data:
        return ""
    return _fernet().encrypt(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode()


def decrypt_credentials(blob: str) -> dict:
    import json

    if not blob:
        return {}
    try:
        return json.loads(_fernet().decrypt(blob.encode()).decode("utf-8"))
    except (InvalidToken, ValueError):
        return {}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 6:
        return "•" * len(value)
    return value[:3] + "•" * (len(value) - 6) + value[-3:]
