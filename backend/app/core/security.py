from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid

from sqlalchemy.orm import Session

from app.db.models import ApiKey

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    ok, _updated = verify_and_update_password(password, password_hash)
    return ok


def verify_and_update_password(password: str, stored_hash: str) -> tuple[bool, str | None]:
    try:
        return password_hasher.verify_and_update(password, stored_hash)
    except UnknownHashError:
        return False, None


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_api_key_token(*, tenant_id: str, name: str) -> tuple[str, ApiKey]:
    # Token format: sk_<prefix>_<secret>
    prefix = secrets.token_hex(4)  # 8 hex chars
    secret = secrets.token_urlsafe(24)
    token = f"sk_{prefix}_{secret}"

    salt = secrets.token_hex(16)
    digest = _sha256_hex(f"{salt}:{token}".encode("utf-8"))

    api_key = ApiKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        key_prefix=f"sk_{prefix}_",
        key_salt=salt,
        key_hash=digest,
        is_active=True,
    )
    return token, api_key


def create_api_key_from_token(*, tenant_id: str, name: str, token: str) -> ApiKey:
    if not token.startswith("sk_") or "_" not in token[3:]:
        raise ValueError("Invalid API key token format")
    prefix_end = token.find("_", 3)
    prefix = token[: prefix_end + 1]
    if len(prefix) > 16:
        raise ValueError("API key prefix too long")
    salt = secrets.token_hex(16)
    digest = _sha256_hex(f"{salt}:{token}".encode("utf-8"))
    return ApiKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        name=name,
        key_prefix=prefix,
        key_salt=salt,
        key_hash=digest,
        is_active=True,
    )


def verify_api_key(db: Session, presented_token: str) -> ApiKey | None:
    # Lookup by prefix to avoid scanning all keys.
    prefix_end = presented_token.find("_", 3)
    if prefix_end == -1:
        return None
    # Expect 'sk_' + 8 hex + '_'
    prefix = presented_token[: prefix_end + 1]
    api_key = db.query(ApiKey).filter(ApiKey.key_prefix == prefix, ApiKey.is_active.is_(True)).one_or_none()
    if not api_key:
        return None
    digest = _sha256_hex(f"{api_key.key_salt}:{presented_token}".encode("utf-8"))
    if not hmac.compare_digest(digest, api_key.key_hash):
        return None
    return api_key


def sha256_text(text: str) -> str:
    return _sha256_hex(text.encode("utf-8"))
