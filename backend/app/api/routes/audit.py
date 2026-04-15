from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Query, Response
from fastapi import Depends
from fastapi.responses import StreamingResponse
from fastapi import HTTPException, status
from sqlalchemy import func

from app.api.deps import DbDep, require_role
from app.core.presets import get_product_name, get_terminology
from app.core.roles import canonical_role
from app.core.errors import ApiError
from app.db.models import ApiKey, AuditEvent, Tenant, User
from app.services.audit_integrity import resolve_integrity_tenant_id, verify_audit_chain
from app.services.audit_log import write_admin_audit_event
from app.services.audit_reports import REPORT_VERSION, build_audit_report_context, render_audit_report_html
from app.services.fhir_audit import to_fhir_audit_event
from app.services.phi import confidentiality_exposure_level

router = APIRouter()
integrity_router = APIRouter()

AuditReader = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "operator", "reviewer", "auditor"))]
AuditExporter = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "auditor"))]
AuditVerifier = Annotated[User, Depends(require_role("super_admin", "org_admin", "compliance_admin", "auditor"))]


def _filtered_audit_rows(
    db,
    *,
    tenant_id: str,
    start: Optional[datetime],
    end: Optional[datetime],
    action_type: Optional[str],
    outcome: Optional[str],
    severity: Optional[str],
    api_key_id: Optional[str],
    user_id: Optional[str],
    practice_group: Optional[str],
    matter_id: Optional[str],
    matter_query: Optional[str],
    flag: Optional[str],
    limit: int = 5000,
) -> list[AuditEvent]:
    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    q = _apply_filters(
        q,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )
    return q.order_by(AuditEvent.timestamp.desc()).limit(limit).all()


def _resolve_tenant_name(db, *, tenant_id: str) -> str:
    tenant = db.get(Tenant, tenant_id)
    terminology = get_terminology()
    org_label = str(terminology.get("organization_singular") or "Organization")
    return tenant.name if tenant else f"{get_product_name()} {org_label}"


def _build_report_context(
    db,
    *,
    tenant_id: str,
    start: Optional[datetime],
    end: Optional[datetime],
    action_type: Optional[str],
    outcome: Optional[str],
    severity: Optional[str],
    api_key_id: Optional[str],
    user_id: Optional[str],
    practice_group: Optional[str],
    matter_id: Optional[str],
    matter_query: Optional[str],
    flag: Optional[str],
    include_summary: bool,
) -> dict:
    rows = _filtered_audit_rows(
        db,
        tenant_id=tenant_id,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )
    items = _enrich_events(db, rows, tenant_id=tenant_id)
    return build_audit_report_context(
        firm_name=_resolve_tenant_name(db, tenant_id=tenant_id),
        events=items,
        start=start,
        end=end,
        matter_query=matter_query or matter_id,
        practice_group=practice_group,
        include_summary=include_summary,
    )

def _enrich_events(db, events: list[AuditEvent], *, tenant_id: str) -> list[dict]:
    user_ids = {e.user_id for e in events if e.user_id}
    api_key_ids = {e.api_key_id for e in events if e.api_key_id}

    users_by_id: dict[str, User] = {}
    if user_ids:
        rows = (
            db.query(User)
            .filter(User.id.in_(list(user_ids)))
            .filter((User.tenant_id == tenant_id) | (User.role == "super_admin"))
            .all()
        )
        for u in rows:
            users_by_id[u.id] = u

    api_keys_by_id: dict[str, ApiKey] = {}
    if api_key_ids:
        rows = db.query(ApiKey).filter(ApiKey.id.in_(list(api_key_ids)), ApiKey.tenant_id == tenant_id).all()
        for k in rows:
            api_keys_by_id[k.id] = k

    enriched: list[dict] = []
    for e in events:
        d = e.to_dict()
        d["confidentiality_exposure_level"] = confidentiality_exposure_level(e.phi_score)
        u = users_by_id.get(e.user_id) if e.user_id else None
        k = api_keys_by_id.get(e.api_key_id) if e.api_key_id else None
        d["user_email"] = u.email if u else None
        d["user_role"] = canonical_role(u.role) if u else None
        d["api_key_name"] = k.name if k else None
        if u:
            d["actor"] = {"type": "user", "user_id": u.id, "email": u.email, "role": canonical_role(u.role)}
        elif k:
            d["actor"] = {"type": "api_key", "api_key_id": k.id, "name": k.name}
        else:
            d["actor"] = {"type": "system"}
        enriched.append(d)
    return enriched


def _apply_filters(
    q,
    *,
    start: Optional[datetime],
    end: Optional[datetime],
    action_type: Optional[str],
    outcome: Optional[str],
    severity: Optional[str],
    api_key_id: Optional[str],
    user_id: Optional[str],
    practice_group: Optional[str],
    matter_id: Optional[str],
    matter_query: Optional[str],
    flag: Optional[str],
):
    if start:
        q = q.filter(AuditEvent.timestamp >= start)
    if end:
        q = q.filter(AuditEvent.timestamp <= end)
    if action_type:
        q = q.filter(AuditEvent.action_type == action_type)
    if outcome:
        q = q.filter(AuditEvent.outcome == outcome)
    if severity:
        q = q.filter(AuditEvent.severity == severity)
    if api_key_id:
        q = q.filter(AuditEvent.api_key_id == api_key_id)
    if user_id:
        q = q.filter(AuditEvent.user_id == user_id)
    if practice_group:
        q = q.filter(AuditEvent.practice_group == practice_group)
    if matter_id:
        q = q.filter(AuditEvent.matter_id == matter_id)
    if matter_query:
        q = q.filter(AuditEvent.matter_id.isnot(None), AuditEvent.matter_id.ilike(f"%{matter_query}%"))
    if flag:
        q = q.filter(AuditEvent.risk_flags.contains([flag]))
    return q


@router.get("", response_model=list[dict])
def list_audit_events(
    db: DbDep,
    user: AuditReader,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
) -> list[dict]:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    q = _apply_filters(
        q,
        start=start,
        end=end,
        action_type=action_type,
        outcome=None,
        severity=None,
        api_key_id=None,
        user_id=None,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=None,
    )
    rows = q.order_by(AuditEvent.timestamp.desc()).limit(500).all()
    return _enrich_events(db, rows, tenant_id=tenant_id)


@router.get("/search", response_model=dict)
def search_audit_events(
    db: DbDep,
    user: AuditReader,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    q = db.query(AuditEvent).filter(AuditEvent.tenant_id == tenant_id)
    q = _apply_filters(
        q,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )

    limit = max(1, min(200, limit))
    offset = max(0, offset)
    total = q.with_entities(func.count(AuditEvent.id)).scalar() or 0
    rows = q.order_by(AuditEvent.timestamp.desc()).limit(limit).offset(offset).all()
    return {"items": _enrich_events(db, rows, tenant_id=tenant_id), "total": int(total), "limit": limit, "offset": offset}


@router.get("/export.csv")
def export_csv(
    db: DbDep,
    user: AuditExporter,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
) -> StreamingResponse:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    rows = _filtered_audit_rows(
        db,
        tenant_id=tenant_id,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )
    try:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=AuditEvent.csv_fields())
        writer.writeheader()
        for r in rows:
            writer.writerow(r.to_csv_row())
        payload = buf.getvalue()
    except Exception as exc:
        raise ApiError(status_code=500, code="EXPORT_FAILED", detail="CSV export generation failed") from exc

    return StreamingResponse(iter([payload]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=audit_events.csv"})


@router.get("/export.json")
def export_json(
    db: DbDep,
    user: AuditExporter,
    format: str = "sentinel",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
) -> Response:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    rows = _filtered_audit_rows(
        db,
        tenant_id=tenant_id,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )
    try:
        if format == "fhir":
            payload = [to_fhir_audit_event(r) for r in rows]
        else:
            payload = _enrich_events(db, rows, tenant_id=tenant_id)
        return Response(content=AuditEvent.json_dumps(payload), media_type="application/json")
    except Exception as exc:
        raise ApiError(status_code=500, code="EXPORT_FAILED", detail="JSON export generation failed") from exc

@router.get("/export.pdf")
def export_pdf(
    db: DbDep,
    user: AuditExporter,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
) -> Response:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")

    rows = _filtered_audit_rows(
        db,
        tenant_id=tenant_id,
        start=start,
        end=end,
        action_type=action_type,
        outcome=outcome,
        severity=severity,
        api_key_id=api_key_id,
        user_id=user_id,
        practice_group=practice_group,
        matter_id=matter_id,
        matter_query=matter_query,
        flag=flag,
    )
    items = _enrich_events(db, rows, tenant_id=tenant_id)

    # Local import so deployments without this feature can fail fast at build time.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def actor_label(ev: dict) -> str:
        actor = ev.get("actor") or {}
        if actor.get("type") == "user":
            return str(actor.get("email") or actor.get("user_id") or "user")
        if actor.get("type") == "api_key":
            return str(actor.get("name") or actor.get("api_key_id") or "api_key")
        return "system"

    styles = getSampleStyleSheet()
    normal = styles["Normal"]

    data: list[list[object]] = [
        ["Timestamp", "Actor", "Model", "Outcome", "Risk Flags", "Confidentiality Level"],
    ]
    if not items:
        data.append([Paragraph("No audit events match the selected filters.", normal), "", "", "", "", ""])
    for ev in items:
        ts = str(ev.get("timestamp") or "")
        actor = actor_label(ev)
        model = str(ev.get("model") or "")
        out = str(ev.get("outcome") or "")
        flags = ev.get("risk_flags") or []
        flags_text = ", ".join([str(x) for x in flags]) if isinstance(flags, list) else str(flags)
        level = str(ev.get("confidentiality_exposure_level") or "")
        data.append(
            [
                Paragraph(ts, normal),
                Paragraph(actor, normal),
                Paragraph(model, normal),
                Paragraph(out, normal),
                Paragraph(flags_text, normal),
                Paragraph(level, normal),
            ]
        )

    try:
        product_name = get_product_name()
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(letter),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24,
            title=f"{product_name} Audit Export",
        )
        table = Table(
            data,
            repeatRows=1,
            colWidths=[110, 150, 120, 70, 230, 110],
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("ALIGN", (0, 0), (-1, 0), "LEFT"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("FONTSIZE", (0, 1), (-1, -1), 8),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story = [
            Paragraph(f"{product_name} — AI Activity Log Export", styles["Title"]),
            Spacer(1, 8),
            Paragraph(f"Rows: {len(items)}", normal),
            Spacer(1, 12),
            table,
        ]
        doc.build(story)
        pdf_bytes = buf.getvalue()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=sentinel_audit_events.pdf"},
        )
    except Exception as exc:
        raise ApiError(status_code=500, code="EXPORT_FAILED", detail="PDF export generation failed") from exc


@router.get("/report.html")
def export_report_html(
    db: DbDep,
    user: AuditExporter,
    include_summary: bool = True,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
) -> Response:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    try:
        context = _build_report_context(
            db,
            tenant_id=tenant_id,
            start=start,
            end=end,
            action_type=action_type,
            outcome=outcome,
            severity=severity,
            api_key_id=api_key_id,
            user_id=user_id,
            practice_group=practice_group,
            matter_id=matter_id,
            matter_query=matter_query,
            flag=flag,
            include_summary=include_summary,
        )
        html = render_audit_report_html(context)
        return Response(
            content=html,
            media_type="text/html; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=sentinel_audit_report.html"},
        )
    except Exception as exc:
        raise ApiError(status_code=500, code="EXPORT_FAILED", detail="Audit report HTML generation failed") from exc


@router.get("/report.pdf")
def export_report_pdf(
    db: DbDep,
    user: AuditExporter,
    include_summary: bool = True,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    action_type: Optional[str] = None,
    outcome: Optional[str] = None,
    severity: Optional[str] = None,
    api_key_id: Optional[str] = None,
    user_id: Optional[str] = None,
    practice_group: Optional[str] = None,
    matter_id: Optional[str] = None,
    matter_query: Optional[str] = None,
    flag: Optional[str] = None,
) -> Response:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    try:
        product_name = get_product_name()
        terminology = get_terminology()
        org_label = str(terminology.get("organization_singular") or "Organization")
        primary_label = str((terminology.get("workflow") or {}).get("primary_entity_label") or "Work Item")
        secondary_label = str((terminology.get("workflow") or {}).get("secondary_entity_label") or "Workstream")
        report_label = str(terminology.get("report_label") or "Audit Report")
        primary_plural = primary_label if primary_label.endswith("s") else f"{primary_label}s"
        secondary_plural = secondary_label if secondary_label.endswith("s") else f"{secondary_label}s"
        context = _build_report_context(
            db,
            tenant_id=tenant_id,
            start=start,
            end=end,
            action_type=action_type,
            outcome=outcome,
            severity=severity,
            api_key_id=api_key_id,
            user_id=user_id,
            practice_group=practice_group,
            matter_id=matter_id,
            matter_query=matter_query,
            flag=flag,
            include_summary=include_summary,
        )

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="SmallMuted", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#475569")))
        styles.add(ParagraphStyle(name="SectionHeading", parent=styles["Heading2"], fontSize=14, textColor=colors.HexColor("#0f172a"), spaceAfter=8))

        summary_cards = [
            ["Total events", str(context["summary_metrics"]["total_events"])],
            ["Flagged events", str(context["summary_metrics"]["flagged_events"])],
            ["Blocked requests", str(context["summary_metrics"]["blocked_requests"])],
            [f"Unique {primary_plural}", str(context["summary_metrics"]["unique_matters"])],
            [secondary_plural, str(context["summary_metrics"]["practice_groups"])],
            ["Estimated cost (USD)", f'{float(context["summary_metrics"]["total_cost_usd"]):,.2f}'],
        ]

        def make_counter_table(title: str, rows: list[dict[str, Any]], empty: str) -> list:
            flow = [Paragraph(title, styles["SectionHeading"])]
            if not rows:
                flow.append(Paragraph(empty, styles["SmallMuted"]))
                flow.append(Spacer(1, 8))
                return flow
            data = [["Label", "Count"]] + [[str(row["label"]), str(row["count"])] for row in rows]
            table = Table(data, colWidths=[4.8 * inch, 1.2 * inch])
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ]
                )
            )
            flow.extend([table, Spacer(1, 10)])
            return flow

        appendix_data = [[
            "Timestamp",
            "Request",
            "Action",
            "Outcome",
            primary_label,
            secondary_label,
            "Provider/Model",
            "Flags",
        ]]
        for item in context["appendix"]:
            appendix_data.append(
                [
                    str(item.get("timestamp") or ""),
                    str(item.get("request_id") or ""),
                    str(item.get("action_type") or ""),
                    str(item.get("outcome") or ""),
                    str(item.get("matter_id") or "—"),
                    str(item.get("practice_group") or "—"),
                    f'{item.get("provider") or "—"} / {item.get("model") or "—"}',
                    ", ".join(item.get("flags") or []) or "—",
                ]
            )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
            title=f"{product_name} {report_label}",
        )
        story = [
            Paragraph(product_name, styles["Heading2"]),
            Paragraph(report_label, styles["Title"]),
            Paragraph(
                f'{org_label}: {context["firm_name"]}<br/>'
                f'Date range: {context["date_range"]["start_label"]} to {context["date_range"]["end_label"]}<br/>'
                f'{primary_label} filter: {context["filters"]["matter_query"] or f"All {primary_plural.lower()}"}<br/>'
                f'{secondary_label}: {context["filters"]["practice_group"] or f"All {secondary_plural.lower()}"}<br/>'
                f'Exported: {context["export_timestamp_label"]}<br/>'
                f'Report version: {REPORT_VERSION}',
                styles["BodyText"],
            ),
            Spacer(1, 14),
        ]
        if include_summary:
            summary_table = Table(summary_cards, colWidths=[3.8 * inch, 2.2 * inch])
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                    ]
                )
            )
            story.extend([Paragraph("Summary Metrics", styles["SectionHeading"]), summary_table, Spacer(1, 12)])
            story.extend(make_counter_table("Flagged Events Summary", context["flagged_summary"], "No flagged events in this scope."))
            story.extend(make_counter_table("Blocked Requests Summary", context["blocked_summary"], "No blocked requests in this scope."))
            story.extend(make_counter_table(f"Top {primary_plural}", context["top_matters"], f"No {primary_label.lower()} values were recorded in this scope."))
            story.extend(make_counter_table(f"Top {secondary_plural}", context["top_practice_groups"], f"No {secondary_label.lower()} values were recorded in this scope."))

        story.extend([PageBreak(), Paragraph("Detailed Event Appendix", styles["SectionHeading"])])
        appendix_table = Table(
            appendix_data,
            repeatRows=1,
            colWidths=[1.15 * inch, 0.95 * inch, 0.9 * inch, 0.7 * inch, 0.9 * inch, 1.05 * inch, 1.1 * inch, 1.25 * inch],
        )
        appendix_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 7),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(appendix_table)
        doc.build(story)
        return Response(
            content=buf.getvalue(),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=sentinel_audit_report.pdf"},
        )
    except Exception as exc:
        raise ApiError(status_code=500, code="EXPORT_FAILED", detail="Audit report PDF generation failed") from exc


@router.get("/{event_id}", response_model=dict)
def get_event(event_id: str, db: DbDep, user: AuditReader) -> dict:
    tenant_id = user.effective_tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant context required")
    ev = db.query(AuditEvent).filter(AuditEvent.id == event_id, AuditEvent.tenant_id == tenant_id).one_or_none()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _enrich_events(db, [ev], tenant_id=tenant_id)[0]


@integrity_router.get("/verify", response_model=dict)
def verify_integrity(
    db: DbDep,
    user: AuditVerifier,
    from_: Annotated[Optional[datetime], Query(alias="from")] = None,
    to: Optional[datetime] = None,
    tenant_id: Optional[str] = None,
) -> dict:
    resolved_tenant_id = resolve_integrity_tenant_id(
        user_tenant_id=user.effective_tenant_id,
        user_role=user.role,
        query_tenant_id=tenant_id,
    )
    result = verify_audit_chain(db, tenant_id=resolved_tenant_id, start=from_, end=to)
    write_admin_audit_event(
        db,
        tenant_id=resolved_tenant_id,
        user_id=user.id,
        action_type="AUDIT_VERIFY_RUN",
        outcome="success" if result["chain_valid"] else "fail",
        reason="Audit integrity verified" if result["chain_valid"] else "Audit integrity verification found a broken chain",
        event_data={
            "from": from_.isoformat() if from_ else None,
            "to": to.isoformat() if to else None,
            **result,
        },
    )
    return result
