import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from fastapi import HTTPException


def telegram_user(header: str, token: str) -> int:
    try:
        scheme, raw = header.split(" ", 1)
        if scheme != "tma" or not token:
            raise ValueError()
        pairs = parse_qsl(raw, strict_parsing=True)
        values = dict(pairs)
        if len(values) != len(pairs):
            raise ValueError()
        received = values.pop("hash")
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(received, expected):
            raise ValueError()
        age = time.time() - int(values["auth_date"])
        if age < -30 or age > 86400:
            raise ValueError()
        user_id = json.loads(values["user"])["id"]
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            raise ValueError()
        return user_id
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, "Откройте приложение заново из Telegram")
