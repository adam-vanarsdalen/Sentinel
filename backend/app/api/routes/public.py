from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from pydantic import model_validator

from app.api.deps import DbDep
from app.core.presets import build_public_app_config
from app.db.models import TrialRequest

router = APIRouter()


class TrialRequestIn(BaseModel):
    organization_name: str | None = Field(default=None, min_length=1, max_length=200)
    firm_name: str | None = Field(default=None, min_length=1, max_length=200)
    contact_name: str = Field(min_length=1, max_length=200)
    email: EmailStr

    @field_validator("organization_name", "firm_name", "contact_name")
    @classmethod
    def _strip_and_require_non_empty(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v

    @model_validator(mode="after")
    def _require_org_name(self):
        if not ((self.organization_name or "").strip() or (self.firm_name or "").strip()):
            raise ValueError("organization_name or firm_name is required")
        return self

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: EmailStr) -> str:
        # Normalize without changing validation semantics (EmailStr validation already applied).
        return str(v).strip().lower()


@router.post("/trial-requests", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_trial_request(req: TrialRequestIn, db: DbDep) -> dict:
    organization_name = (req.organization_name or req.firm_name or "").strip()
    row = TrialRequest(
        id=str(uuid.uuid4()),
        firm_name=organization_name,
        contact_name=req.contact_name,
        email=str(req.email),
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    return {"ok": True, "id": row.id}


@router.get("/app-config", response_model=dict)
def get_app_config() -> dict:
    return build_public_app_config()
