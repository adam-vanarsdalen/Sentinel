from __future__ import annotations


def test_health_alias_returns_liveness_payload(client):
    response = client.get("/health")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert "version" in body
    assert body["preset_id"] == "general"
    assert body["product_name"] == "Sentinel"


def test_ready_alias_returns_dependency_checks(client, monkeypatch):
    class _RedisStub:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr("app.api.routes.health.Redis.from_url", lambda _url: _RedisStub())
    monkeypatch.setattr("app.api.routes.health.settings.seed_demo", False)
    monkeypatch.setattr("app.api.routes.health.settings.ollama_enabled", False)

    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True
    assert body["checks"]["ollama"]["ok"] is True
    assert body["checks"]["ollama"]["skipped"] is True


def test_ready_checks_ollama_when_enabled(client, monkeypatch):
    class _RedisStub:
        def ping(self) -> bool:
            return True

    class _Response:
        status_code = 200
        content = b'{"version":"0.11.0"}'

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"version": "0.11.0"}

    monkeypatch.setattr("app.api.routes.health.Redis.from_url", lambda _url: _RedisStub())
    monkeypatch.setattr("app.api.routes.health.settings.seed_demo", False)
    monkeypatch.setattr("app.api.routes.health.settings.ollama_enabled", True)
    monkeypatch.setattr("app.api.routes.health.settings.ollama_base_url", "http://localhost:11434/v1/")
    monkeypatch.setattr("app.api.routes.health.httpx.get", lambda *args, **kwargs: _Response())

    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["checks"]["ollama"]["ok"] is True
    assert body["checks"]["ollama"]["version"] == "0.11.0"
