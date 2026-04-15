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

    response = client.get("/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True
