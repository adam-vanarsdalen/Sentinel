import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    action_limit_session: Mapped[int] = mapped_column(Integer, default=1000)
    budget_hourly_usd: Mapped[float | None] = mapped_column(Numeric(10, 4))
    budget_daily_usd: Mapped[float | None] = mapped_column(Numeric(10, 4))
    budget_monthly_usd: Mapped[float | None] = mapped_column(Numeric(10, 4))
    allowed_models: Mapped[list] = mapped_column(ARRAY(String), default=list)
    forbidden_endpoints: Mapped[list] = mapped_column(ARRAY(String), default=list)
    forbidden_data_classes: Mapped[list] = mapped_column(ARRAY(String), default=list)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
