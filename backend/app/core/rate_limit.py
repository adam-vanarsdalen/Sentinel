from __future__ import annotations

import logging
import hashlib
import time

from fastapi import HTTPException, status
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _hit(key: str, limit: int, window_seconds: int = 60) -> bool:
    try:
        r = _redis()
        now_bucket = int(time.time() // window_seconds)
        redis_key = f"rl:{key}:{now_bucket}"
        n = r.incr(redis_key)
        if n == 1:
            r.expire(redis_key, window_seconds + 5)
        if n > limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        return True
    except (RedisConnectionError, RedisTimeoutError) as e:
        logger.warning(f"Rate limiter Redis unavailable; failing open: {e}")
        return False


def enforce_rate_limits(
    *,
    tenant_id: str,
    api_key_id: str,
    tenant_per_minute: int | None = None,
    api_key_per_minute: int | None = None,
) -> None:
    _hit(f"tenant:{tenant_id}", tenant_per_minute or settings.rate_limit_tenant_per_minute)
    _hit(f"apikey:{api_key_id}", api_key_per_minute or settings.rate_limit_apikey_per_minute)


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


def enforce_login_rate_limits(
    *,
    ip_address: str,
    identifier: str,
    ip_per_minute: int | None = None,
    identifier_per_minute: int | None = None,
) -> None:
    _hit(f"login:ip:{ip_address}", ip_per_minute or settings.rate_limit_login_ip_per_minute)
    _hit(
        f"login:identifier:{_hash_identifier(identifier)}",
        identifier_per_minute or settings.rate_limit_login_identifier_per_minute,
    )
