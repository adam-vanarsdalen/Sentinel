from __future__ import annotations


def test_development_metrics_access_is_open_without_token(client, monkeypatch):
    monkeypatch.setattr("app.core.metrics.settings.environment", "development")
    monkeypatch.setattr("app.core.metrics.settings.metrics_token", None)

    response = client.get("/metrics")

    assert response.status_code == 200, response.text
    assert "sentinel_http_requests_total" in response.text


def test_production_metrics_without_token_is_not_public(client, monkeypatch):
    monkeypatch.setattr("app.core.metrics.settings.environment", "production")
    monkeypatch.setattr("app.core.metrics.settings.metrics_token", None)

    response = client.get("/metrics")

    assert response.status_code == 404


def test_production_metrics_with_valid_token(client, monkeypatch):
    monkeypatch.setattr("app.core.metrics.settings.environment", "production")
    monkeypatch.setattr("app.core.metrics.settings.metrics_token", "metrics-secret")

    response = client.get("/metrics", headers={"X-Metrics-Token": "metrics-secret"})

    assert response.status_code == 200, response.text
    assert "sentinel_http_requests_total" in response.text


def test_metrics_invalid_token_is_rejected(client, monkeypatch):
    monkeypatch.setattr("app.core.metrics.settings.environment", "production")
    monkeypatch.setattr("app.core.metrics.settings.metrics_token", "metrics-secret")

    response = client.get("/metrics", headers={"X-Metrics-Token": "wrong"})

    assert response.status_code == 404


def test_metrics_use_route_templates_for_path_labels(client, monkeypatch):
    monkeypatch.setattr("app.core.metrics.settings.environment", "development")
    monkeypatch.setattr("app.core.metrics.settings.metrics_token", None)

    client.get("/this-path-should-not-become-a-metric-label")
    response = client.get("/metrics")

    assert response.status_code == 200, response.text
    assert 'path="__unmatched__"' in response.text
    assert "this-path-should-not-become-a-metric-label" not in response.text
