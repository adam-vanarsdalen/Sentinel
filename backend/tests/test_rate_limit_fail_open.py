from __future__ import annotations

from redis.exceptions import ConnectionError as RedisConnectionError


def test_rate_limiter_fails_open_on_redis_connection_error(monkeypatch):
    import app.core.rate_limit as rl

    def _boom():
        raise RedisConnectionError("redis down")

    monkeypatch.setattr(rl, "_redis", _boom)

    ok = rl._hit("tenant:t1", limit=1)  # type: ignore[attr-defined]
    assert ok is False

