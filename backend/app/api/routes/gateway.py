from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import ApiKeyAuth, DbDep
from app.core.errors import error_response
from app.core.presets import get_terminology
from app.core.rate_limit import enforce_rate_limits
from app.db.models import TenantPolicy
from app.services.policy import DEFAULT_POLICY
from app.services.gateway import RequestBlocked, handle_chat_completion

router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    messages: list[ChatMessage] = Field(min_length=1)
    max_tokens: int | None = None
    temperature: float | None = None
    metadata: dict | None = None


@router.post("/chat/completions")
def chat_completions(
    req: ChatCompletionRequest,
    db: DbDep,
    api_key: ApiKeyAuth,
    x_matter_id: Annotated[Optional[str], Header()] = None,
    x_practice_group: Annotated[Optional[str], Header()] = None,
    x_client_name: Annotated[Optional[str], Header()] = None,
    x_work_item_id: Annotated[Optional[str], Header()] = None,
    x_workstream: Annotated[Optional[str], Header()] = None,
    x_external_party_name: Annotated[Optional[str], Header()] = None,
) -> dict:
    if not api_key.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key revoked")
    # Policy-aware rate limits (fallback to global settings).
    policy_row = db.get(TenantPolicy, api_key.tenant_id)
    policy = policy_row.policy_json if policy_row else DEFAULT_POLICY
    rate_limits = policy.get("rate_limits") if isinstance(policy, dict) else None
    tenant_per_minute = rate_limits.get("tenant_per_minute") if isinstance(rate_limits, dict) else None
    api_key_per_minute = rate_limits.get("api_key_per_minute") if isinstance(rate_limits, dict) else None
    enforce_rate_limits(
        tenant_id=api_key.tenant_id,
        api_key_id=api_key.id,
        tenant_per_minute=tenant_per_minute,
        api_key_per_minute=api_key_per_minute,
    )
    payload = req.model_dump()
    metadata = payload.get("metadata") or {}
    if metadata.get("work_item_id") and not metadata.get("matter_id"):
        metadata["matter_id"] = metadata["work_item_id"]
    if metadata.get("workstream") and not metadata.get("practice_group"):
        metadata["practice_group"] = metadata["workstream"]
    if metadata.get("external_party_name") and not metadata.get("client_name"):
        metadata["client_name"] = metadata["external_party_name"]
    if x_matter_id and not metadata.get("matter_id"):
        metadata["matter_id"] = x_matter_id
    if x_work_item_id and not metadata.get("matter_id"):
        metadata["matter_id"] = x_work_item_id
    if x_practice_group and not metadata.get("practice_group"):
        metadata["practice_group"] = x_practice_group
    if x_workstream and not metadata.get("practice_group"):
        metadata["practice_group"] = x_workstream
    if x_client_name and not metadata.get("client_name"):
        metadata["client_name"] = x_client_name
    if x_external_party_name and not metadata.get("client_name"):
        metadata["client_name"] = x_external_party_name
    payload["metadata"] = metadata or None
    try:
        return handle_chat_completion(db=db, api_key=api_key, req=payload)
    except RequestBlocked as e:
        extra = {
            "outcome": "BLOCKED",
            "block_reason": e.block_reason,
            "reason_code": e.reason_code,
            "block_stage": e.block_stage,
            "flags": e.flags,
            "policy": {
                "updated_at": e.policy_updated_at,
                "version_id": e.policy_version_id,
                "source_template_id": e.policy_source_template_id,
                "rule": e.rule,
                "reason_code": e.reason_code,
                "block_stage": e.block_stage,
            },
        }
        if e.provider is not None:
            extra["provider"] = e.provider
        if e.model is not None:
            extra["model"] = e.model
        if e.security is not None:
            extra["security"] = e.security
        return error_response(
            status_code=e.status_code,
            code=e.error_code,
            message=str((get_terminology().get("messages") or {}).get("blocked_by_rules") or "Blocked by AI Rules."),
            detail=e.block_reason,
            retryable=e.retryable,
            extra=extra,
        )
