from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import parse_qsl

from app.config import settings


class TelegramAuthError(ValueError):
    pass


def validate_init_data(init_data: str, max_age_seconds: int = 86400) -> int:
    if not init_data or not settings.telegram_bot_token:
        raise TelegramAuthError("telegram init data is unavailable")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", "")
    if not received_hash:
        raise TelegramAuthError("telegram hash is missing")

    data_check_string = "\n".join(
        f"{key}={pairs[key]}" for key in sorted(pairs)
    )
    secret_key = hmac.new(
        b"WebAppData",
        settings.telegram_bot_token.encode(),
        hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("telegram signature is invalid")

    try:
        auth_date = int(pairs["auth_date"])
        user_id = int(__import__("json").loads(pairs["user"])["id"])
    except (KeyError, ValueError, TypeError, __import__("json").JSONDecodeError) as exc:
        raise TelegramAuthError("telegram user data is invalid") from exc

    if auth_date > int(time.time()) + 60:
        raise TelegramAuthError("telegram auth date is in the future")
    if int(time.time()) - auth_date > max_age_seconds:
        raise TelegramAuthError("telegram auth data is expired")
    return user_id
