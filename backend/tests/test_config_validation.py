from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _valid_production_settings(**overrides):
    values = {
        "environment": "production",
        "jwt_secret": "j" * 32,
        "sentinel_secret_key": "s" * 32,
        "cors_origins": "https://sentinel.example.com",
        "seed_demo": False,
        "demo_super_admin_password": "super-admin-production-password",
        "demo_tenant_admin_password": "tenant-admin-production-password",
        "provider_default": "openai",
        "metrics_token": "metrics-production-token",
    }
    values.update(overrides)
    return values


def _assert_invalid(message: str, **overrides):
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, **_valid_production_settings(**overrides))
    assert message in str(excinfo.value)


def test_valid_production_settings_are_accepted():
    settings = Settings(_env_file=None, **_valid_production_settings())
    assert settings.environment == "production"


@pytest.mark.parametrize("jwt_secret", ["", "dev", "short"])
def test_production_rejects_missing_default_or_short_jwt_secret(jwt_secret: str):
    _assert_invalid("JWT_SECRET", jwt_secret=jwt_secret)


@pytest.mark.parametrize("sentinel_secret_key", ["", "short"])
def test_production_rejects_missing_or_short_sentinel_secret_key(sentinel_secret_key: str):
    _assert_invalid("SENTINEL_SECRET_KEY", sentinel_secret_key=sentinel_secret_key)


@pytest.mark.parametrize("cors_origins", ["*", "https://app.example.com,*"])
def test_production_rejects_wildcard_cors_origins(cors_origins: str):
    _assert_invalid("CORS_ORIGINS includes '*'", cors_origins=cors_origins)


@pytest.mark.parametrize(
    "cors_origins",
    [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://app.example.com,http://localhost:3000",
    ],
)
def test_production_rejects_localhost_cors_origins(cors_origins: str):
    _assert_invalid("CORS_ORIGINS includes localhost or 127.0.0.1", cors_origins=cors_origins)


def test_production_rejects_demo_seeding():
    _assert_invalid("SEED_DEMO must be disabled", seed_demo=True)


@pytest.mark.parametrize("field", ["demo_super_admin_password", "demo_tenant_admin_password"])
def test_production_rejects_default_demo_admin_passwords(field: str):
    _assert_invalid(field.upper(), **{field: "ChangeMe!12345"})


def test_production_rejects_mock_default_provider():
    _assert_invalid("PROVIDER_DEFAULT=mock", provider_default="mock")


def test_production_rejects_missing_metrics_token():
    _assert_invalid("METRICS_TOKEN must be set", metrics_token="")


def test_development_defaults_remain_allowed():
    settings = Settings(_env_file=None, environment="development")
    assert settings.environment == "development"
    assert settings.jwt_secret == "dev"
    assert settings.provider_default == "mock"
