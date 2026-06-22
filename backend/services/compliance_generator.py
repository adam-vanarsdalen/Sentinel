"""Compliance package generator — maps audit entries to regulation controls."""
from __future__ import annotations

import io
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.alert import Alert
from models.audit_entry import AuditEntry
from models.compliance_package import CompliancePackage
from models.request_log import RequestLog
from regulatory.mapper import all_controls

LAYER_NAMES = {
    1: "Layer 1 (Ingestion)",
    2: "Layer 2 (Routing)",
    3: "Layer 3 (Pre-call Enforcement)",
    4: "Layer 4 (Reasoning)",
    5: "Layer 5 (Grounding)",
    6: "Layer 6 (Anomaly Detection)",
    7: "Layer 7 (Compliance Output)",
}


class ComplianceGeneratorService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def generate(
        self,
        tenant_id: str,
        start: datetime,
        end: datetime,
        regulations: list[str],
    ) -> dict[str, Any]:
        tid = uuid.UUID(tenant_id)

        # Fetch audit entries in range
        result = await self._db.execute(
            select(AuditEntry)
            .where(
                AuditEntry.tenant_id == tid,
                AuditEntry.created_at >= start,
                AuditEntry.created_at <= end,
            )
        )
        entries = result.scalars().all()

        # Count request stats
        total = await self._db.scalar(
            select(func.count()).select_from(RequestLog)
            .where(RequestLog.tenant_id == tid, RequestLog.created_at >= start, RequestLog.created_at <= end)
        ) or 0
        blocked = await self._db.scalar(
            select(func.count()).select_from(RequestLog)
            .where(
                RequestLog.tenant_id == tid,
                RequestLog.status == "blocked",
                RequestLog.created_at >= start,
                RequestLog.created_at <= end,
            )
        ) or 0
        anomalies = await self._db.scalar(
            select(func.count()).select_from(Alert)
            .where(
                Alert.tenant_id == tid,
                Alert.alert_type == "anomaly",
                Alert.created_at >= start,
                Alert.created_at <= end,
            )
        ) or 0
        ks_events = await self._db.scalar(
            select(func.count()).select_from(Alert)
            .where(
                Alert.tenant_id == tid,
                Alert.alert_type == "kill_switch",
                Alert.created_at >= start,
                Alert.created_at <= end,
            )
        ) or 0

        # Build evidence index: control_id → list of audit entry IDs
        evidence_index: dict[str, list[int]] = {}
        for entry in entries:
            if entry.status == "error":
                continue
            mappings: dict[str, list[str]] = entry.regulation_mappings or {}
            for reg, controls in mappings.items():
                if reg not in regulations:
                    continue
                for ctrl in controls:
                    evidence_index.setdefault(ctrl, []).append(entry.id)

        # Gap analysis
        controls_universe = all_controls()
        gap_analysis: list[dict[str, Any]] = []
        evidence_sections: list[dict[str, Any]] = []

        for reg, ctrl_list in controls_universe.items():
            if reg not in regulations:
                continue
            for ctrl in ctrl_list:
                refs = evidence_index.get(ctrl, [])
                if refs:
                    evidence_sections.append({
                        "regulation": reg,
                        "control_id": ctrl,
                        "evidence_present": True,
                        "evidence_refs": refs[:100],
                    })
                else:
                    layer_num = self._find_layer_for_control(reg, ctrl)
                    layer_name = LAYER_NAMES.get(layer_num, "unknown layer")
                    gap_analysis.append({
                        "regulation": reg,
                        "control_id": ctrl,
                        "evidence_present": False,
                        "gap_description": (
                            f"No {ctrl} evidence in range. This control is satisfied by "
                            f"{layer_name} events. Ensure {layer_name} is active and processing requests."
                        ),
                    })

        evidence_json: dict[str, Any] = {
            "package_id": str(uuid.uuid4()),
            "generated_at": datetime.utcnow().isoformat(),
            "tenant_id": tenant_id,
            "time_range": {"start": start.isoformat(), "end": end.isoformat()},
            "total_requests": total,
            "blocked_requests": blocked,
            "anomalies_detected": anomalies,
            "kill_switch_events": ks_events,
            "regulations": regulations,
            "evidence_sections": evidence_sections,
            "gap_analysis": gap_analysis,
        }

        pkg = CompliancePackage(
            tenant_id=tid,
            time_range_start=start,
            time_range_end=end,
            regulations=regulations,
            total_requests=total,
            blocked_requests=blocked,
            anomalies_detected=anomalies,
            kill_switch_events=ks_events,
            evidence_json=evidence_json,
            gap_analysis={"gaps": gap_analysis},
        )
        self._db.add(pkg)
        await self._db.commit()
        await self._db.refresh(pkg)
        evidence_json["package_id"] = str(pkg.id)
        return evidence_json

    def _find_layer_for_control(self, regulation: str, control_id: str) -> int:
        from regulatory import colorado_sb205, eu_ai_act, hipaa, nist_ai_rmf
        reg_map = {
            "EU_AI_ACT": eu_ai_act.LAYER_CONTROLS,
            "NIST_AI_RMF": nist_ai_rmf.LAYER_CONTROLS,
            "COLORADO_SB205": colorado_sb205.LAYER_CONTROLS,
            "HIPAA": hipaa.LAYER_CONTROLS,
        }
        layer_controls = reg_map.get(regulation, {})
        for layer, controls in layer_controls.items():
            if control_id in controls:
                return layer
        return 0

    async def get_pdf(self, package_id: str) -> bytes | None:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas as pdf_canvas
        except ImportError:
            return None

        result = await self._db.execute(
            select(CompliancePackage).where(CompliancePackage.id == uuid.UUID(package_id))
        )
        pkg = result.scalar_one_or_none()
        if not pkg:
            return None

        buf = io.BytesIO()
        c = pdf_canvas.Canvas(buf, pagesize=letter)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, 750, "Sentinel Stack Compliance Package")
        c.setFont("Helvetica", 12)
        c.drawString(72, 720, f"Package ID: {pkg.id}")
        c.drawString(72, 700, f"Tenant: {pkg.tenant_id}")
        c.drawString(72, 680, f"Period: {pkg.time_range_start} — {pkg.time_range_end}")
        c.drawString(72, 660, f"Total requests: {pkg.total_requests}")
        c.drawString(72, 640, f"Blocked: {pkg.blocked_requests}")
        c.drawString(72, 620, f"Anomalies: {pkg.anomalies_detected}")
        c.drawString(72, 600, f"Kill switch events: {pkg.kill_switch_events}")

        y = 570
        c.setFont("Helvetica-Bold", 13)
        c.drawString(72, y, "Gap Analysis")
        c.setFont("Helvetica", 10)
        gaps = pkg.gap_analysis.get("gaps", []) if pkg.gap_analysis else []
        for gap in gaps[:20]:
            y -= 18
            if y < 72:
                c.showPage()
                y = 750
            c.drawString(72, y, f"[GAP] {gap.get('regulation')} — {gap.get('control_id')}")
            y -= 14
            desc = gap.get("gap_description", "")
            c.drawString(90, y, desc[:90])

        c.save()
        buf.seek(0)
        return buf.read()
