from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
SECRET_KEY = os.getenv("APP_SECRET_KEY")
TOKEN_TTL_SECONDS = int(os.getenv("ADMIN_TOKEN_TTL_SECONDS", "86400"))

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    raise RuntimeError("必须配置 ADMIN_USERNAME 和 ADMIN_PASSWORD 环境变量")
if not SECRET_KEY:
    raise RuntimeError("必须配置 APP_SECRET_KEY 环境变量")


def _sign(message: str) -> str:
    return hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()


def create_token(username: str) -> str:
    expires = int(time.time()) + TOKEN_TTL_SECONDS
    nonce = secrets.token_urlsafe(12)
    payload = f"{username}:{expires}:{nonce}"
    token = f"{payload}:{_sign(payload)}"
    return base64.urlsafe_b64encode(token.encode()).decode()


def verify_token(token: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        username, expires_raw, nonce, signature = decoded.rsplit(":", 3)
        payload = f"{username}:{expires_raw}:{nonce}"
        expires = int(expires_raw)
    except Exception:
        return False
    if username != ADMIN_USERNAME or expires < int(time.time()):
        return False
    return hmac.compare_digest(signature, _sign(payload))


def verify_login(username: str, password: str) -> bool:
    user_ok = hmac.compare_digest(username, ADMIN_USERNAME)
    password_ok = hmac.compare_digest(password, ADMIN_PASSWORD)
    return user_ok and password_ok
