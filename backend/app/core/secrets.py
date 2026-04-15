from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _derived_secret_seed() -> bytes:
    configured = (settings.sentinel_secret_key or "").strip()
    if configured:
        return configured.encode("utf-8")

    env = (settings.environment or "").strip().lower()
    if env == "production":
        raise RuntimeError("SENTINEL_SECRET_KEY is required in production.")

    # Development-only fallback so the local pilot keeps working without extra setup.
    return f"dev::{settings.jwt_secret}".encode("utf-8")


def _fernet() -> Fernet:
    digest = hashlib.sha256(_derived_secret_seed()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_json(data: dict[str, Any] | None) -> str | None:
    if not data:
        return None
    payload = json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _fernet().encrypt(payload).decode("utf-8")


def decrypt_json(blob: str | None) -> dict[str, Any]:
    if not blob:
        return {}
    try:
        payload = _fernet().decrypt(blob.encode("utf-8"))
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored provider secret") from exc
    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Decrypted provider secret is invalid")
    return data
