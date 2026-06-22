import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CompliancePackage(Base):
    __tablename__ = "compliance_packages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    time_range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    regulations: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
    total_requests: Mapped[int | None] = mapped_column(Integer)
    blocked_requests: Mapped[int | None] = mapped_column(Integer)
    anomalies_detected: Mapped[int | None] = mapped_column(Integer)
    kill_switch_events: Mapped[int | None] = mapped_column(Integer)
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gap_analysis: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
