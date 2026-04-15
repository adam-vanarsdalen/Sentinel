from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from typing import Any

from app.core.presets import get_console_name, get_product_name, get_terminology


REPORT_VERSION = "audit-report-v1"


def _iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _fmt_datetime(value: str | None) -> str:
    if not value:
        return "All available dates"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return value


def _fmt_decimal(value: float | int | Decimal | None) -> str:
    if value is None:
        return "0.00"
    return f"{float(value):,.2f}"


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def build_audit_report_context(
    *,
    firm_name: str,
    events: list[dict],
    start: datetime | None,
    end: datetime | None,
    matter_query: str | None,
    practice_group: str | None,
    include_summary: bool,
) -> dict[str, Any]:
    terminology = get_terminology()
    export_timestamp = _iso(datetime.now(timezone.utc))
    flagged_events = [event for event in events if _as_list(event.get("risk_flags"))]
    blocked_events = [event for event in events if event.get("action_type") == "POLICY_BLOCK" or str(event.get("outcome") or "").lower() == "fail"]
    unique_matters = {str(event.get("matter_id")).strip() for event in events if event.get("matter_id")}
    unique_practice_groups = {str(event.get("practice_group")).strip() for event in events if event.get("practice_group")}
    total_cost = sum(float(event.get("cost_usd") or 0) for event in events)

    flag_counter = Counter()
    for event in flagged_events:
        for flag in _as_list(event.get("risk_flags")):
            flag_counter[flag] += 1

    matter_counter = Counter(
        str(event.get("matter_id")).strip()
        for event in events
        if isinstance(event.get("matter_id"), str) and str(event.get("matter_id")).strip()
    )
    practice_counter = Counter(
        str(event.get("practice_group")).strip()
        for event in events
        if isinstance(event.get("practice_group"), str) and str(event.get("practice_group")).strip()
    )
    blocked_reason_counter = Counter(
        str(event.get("reason") or terminology.get("messages", {}).get("blocked_by_rules") or "Blocked by AI Rules")
        for event in blocked_events
    )

    appendix = []
    for event in events:
        appendix.append(
            {
                "timestamp": event.get("timestamp"),
                "request_id": event.get("request_id") or event.get("id"),
                "action_type": event.get("action_type"),
                "outcome": event.get("outcome"),
                "matter_id": event.get("matter_id"),
                "practice_group": event.get("practice_group"),
                "provider": event.get("provider"),
                "model": event.get("model"),
                "flags": _as_list(event.get("risk_flags")),
                "severity": event.get("severity"),
                "reason": event.get("reason"),
                "confidentiality_exposure_level": event.get("confidentiality_exposure_level"),
            }
        )

    return {
        "report_version": REPORT_VERSION,
        "firm_name": firm_name,
        "product_name": get_product_name(),
        "console_name": get_console_name(),
        "terminology": terminology,
        "date_range": {
            "start": _iso(start),
            "end": _iso(end),
            "start_label": _fmt_datetime(_iso(start)),
            "end_label": _fmt_datetime(_iso(end)),
        },
        "filters": {
            "matter_query": matter_query or None,
            "practice_group": practice_group or None,
        },
        "include_summary": include_summary,
        "export_timestamp": export_timestamp,
        "export_timestamp_label": _fmt_datetime(export_timestamp),
        "summary_metrics": {
            "total_events": len(events),
            "flagged_events": len(flagged_events),
            "blocked_requests": len(blocked_events),
            "unique_matters": len(unique_matters),
            "practice_groups": len(unique_practice_groups),
            "total_cost_usd": total_cost,
        },
        "flagged_summary": [{"label": label, "count": count} for label, count in flag_counter.most_common(8)],
        "blocked_summary": [{"label": label, "count": count} for label, count in blocked_reason_counter.most_common(8)],
        "top_matters": [{"label": label, "count": count} for label, count in matter_counter.most_common(8)],
        "top_practice_groups": [{"label": label, "count": count} for label, count in practice_counter.most_common(8)],
        "appendix": appendix,
    }


def render_audit_report_html(context: dict[str, Any]) -> str:
    terminology = context.get("terminology") or {}
    workflow = terminology.get("workflow") or {}
    org_label = str(terminology.get("organization_singular") or "Organization")
    report_label = str(terminology.get("report_label") or "Audit Report")
    primary_label = str(workflow.get("primary_entity_label") or "Work Item")
    secondary_label = str(workflow.get("secondary_entity_label") or "Workstream")
    product_name = str(context.get("product_name") or "Sentinel")

    def stat_card(label: str, value: str) -> str:
        return (
            '<div class="stat-card">'
            f'<div class="stat-label">{escape(label)}</div>'
            f'<div class="stat-value">{escape(value)}</div>'
            "</div>"
        )

    def summary_list(title: str, rows: list[dict[str, Any]], empty: str) -> str:
        if not rows:
            body = f'<div class="empty">{escape(empty)}</div>'
        else:
            items = "".join(
                f'<tr><td>{escape(str(row["label"]))}</td><td class="count">{int(row["count"])}</td></tr>'
                for row in rows
            )
            body = f'<table class="summary-table"><tbody>{items}</tbody></table>'
        return f'<section class="panel"><h3>{escape(title)}</h3>{body}</section>'

    appendix_rows = "".join(
        "<tr>"
        f'<td>{escape(_fmt_datetime(str(item.get("timestamp") or "")))}</td>'
        f'<td>{escape(str(item.get("request_id") or ""))}</td>'
        f'<td>{escape(str(item.get("action_type") or ""))}</td>'
        f'<td>{escape(str(item.get("outcome") or ""))}</td>'
        f'<td>{escape(str(item.get("matter_id") or "—"))}</td>'
        f'<td>{escape(str(item.get("practice_group") or "—"))}</td>'
        f'<td>{escape(str(item.get("provider") or "—"))}</td>'
        f'<td>{escape(str(item.get("model") or "—"))}</td>'
        f'<td>{escape(", ".join(item.get("flags") or []) or "—")}</td>'
        f'<td>{escape(str(item.get("confidentiality_exposure_level") or "—"))}</td>'
        f'<td>{escape(str(item.get("reason") or "—"))}</td>'
        "</tr>"
        for item in context["appendix"]
    )

    summary_html = ""
    if context["include_summary"]:
        summary_html = (
            '<section class="grid stats">'
            + stat_card("Total events", str(context["summary_metrics"]["total_events"]))
            + stat_card("Flagged events", str(context["summary_metrics"]["flagged_events"]))
            + stat_card("Blocked requests", str(context["summary_metrics"]["blocked_requests"]))
            + stat_card(f"Unique {primary_label.lower()}s", str(context["summary_metrics"]["unique_matters"]))
            + stat_card(f"{secondary_label}s", str(context["summary_metrics"]["practice_groups"]))
            + stat_card("Estimated cost (USD)", _fmt_decimal(context["summary_metrics"]["total_cost_usd"]))
            + "</section>"
            + '<section class="grid summaries">'
            + summary_list("Flagged Events Summary", context["flagged_summary"], "No flagged events in this report scope.")
            + summary_list("Blocked Requests Summary", context["blocked_summary"], "No blocked requests in this report scope.")
            + summary_list(f"Top {primary_label}s", context["top_matters"], f"No {primary_label.lower()} values were recorded in this report scope.")
            + summary_list(
                f"Top {secondary_label}s", context["top_practice_groups"], f"No {secondary_label.lower()} values were recorded in this report scope."
            )
            + "</section>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>{escape(product_name)} {escape(report_label)}</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #0f172a;
        --muted: #475569;
        --line: #cbd5e1;
        --paper: #ffffff;
        --panel: #f8fafc;
        --brand: #0f172a;
        --accent: #8b5e3c;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Georgia", "Times New Roman", serif;
        color: var(--ink);
        background: #eef2f7;
      }}
      .page {{
        max-width: 1180px;
        margin: 24px auto;
        background: var(--paper);
        padding: 32px;
        border: 1px solid var(--line);
        box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
      }}
      .eyebrow {{
        font: 600 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
      }}
      h1, h2, h3 {{ margin: 0; }}
      h1 {{ font-size: 34px; line-height: 1.1; }}
      h2 {{ font-size: 18px; margin-bottom: 12px; }}
      h3 {{ font-size: 15px; margin-bottom: 10px; }}
      p, li, td, th, div {{ font-size: 14px; line-height: 1.45; }}
      .muted {{ color: var(--muted); }}
      .header {{
        display: grid;
        grid-template-columns: 2fr 1fr;
        gap: 24px;
        padding-bottom: 20px;
        border-bottom: 2px solid var(--brand);
      }}
      .meta {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px 18px;
        margin-top: 16px;
      }}
      .meta-label {{
        font: 600 11px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
      .grid {{
        display: grid;
        gap: 16px;
        margin-top: 24px;
      }}
      .stats {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
      .summaries {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .stat-card, .panel {{
        border: 1px solid var(--line);
        background: var(--panel);
        padding: 16px;
      }}
      .stat-label {{
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.08em;
      }}
      .stat-value {{
        font-size: 28px;
        margin-top: 8px;
      }}
      .summary-table, .appendix-table {{
        width: 100%;
        border-collapse: collapse;
      }}
      .summary-table td, .appendix-table td, .appendix-table th {{
        padding: 8px 10px;
        border-bottom: 1px solid var(--line);
        vertical-align: top;
      }}
      .summary-table td.count {{
        text-align: right;
        font-variant-numeric: tabular-nums;
      }}
      .appendix {{
        margin-top: 28px;
      }}
      .appendix-table th {{
        background: var(--brand);
        color: #fff;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        position: sticky;
        top: 0;
      }}
      .appendix-table tr:nth-child(even) td {{
        background: #f8fafc;
      }}
      .empty {{
        color: var(--muted);
      }}
      .footer {{
        margin-top: 20px;
        padding-top: 14px;
        border-top: 1px solid var(--line);
        display: flex;
        justify-content: space-between;
        gap: 12px;
        color: var(--muted);
        font-size: 12px;
      }}
      @media print {{
        body {{ background: #fff; }}
        .page {{
          box-shadow: none;
          border: none;
          margin: 0;
          max-width: none;
          padding: 0;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="page">
      <div class="header">
        <div>
          <div class="eyebrow">{escape(product_name)}</div>
          <h1>{escape(report_label)}</h1>
          <p class="muted">Neutral audit summary for governed AI activity review.</p>
          <div class="meta">
            <div><div class="meta-label">{escape(org_label)}</div><div>{escape(context["firm_name"])}</div></div>
            <div><div class="meta-label">Report version</div><div>{escape(context["report_version"])}</div></div>
            <div><div class="meta-label">Date range</div><div>{escape(context["date_range"]["start_label"])} to {escape(context["date_range"]["end_label"])}</div></div>
            <div><div class="meta-label">Exported</div><div>{escape(context["export_timestamp_label"])}</div></div>
            <div><div class="meta-label">{escape(primary_label)} filter</div><div>{escape(context["filters"]["matter_query"] or f"All {primary_label.lower()}s")}</div></div>
            <div><div class="meta-label">{escape(secondary_label)}</div><div>{escape(context["filters"]["practice_group"] or f"All {secondary_label.lower()}s")}</div></div>
          </div>
        </div>
        <div class="panel">
          <h3>Scope Note</h3>
          <p class="muted">This report reflects {escape(product_name)} audit events within the selected filters. It does not alter the underlying append-only audit trail.</p>
        </div>
      </div>
      {summary_html}
      <section class="appendix">
        <h2>Detailed Event Appendix</h2>
        <table class="appendix-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Request</th>
              <th>Action</th>
              <th>Outcome</th>
              <th>{escape(primary_label)}</th>
              <th>{escape(secondary_label)}</th>
              <th>Provider</th>
              <th>Model</th>
              <th>Flags</th>
              <th>Exposure</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>{appendix_rows or '<tr><td colspan="11" class="empty">No audit events match the selected filters.</td></tr>'}</tbody>
        </table>
      </section>
      <div class="footer">
        <div>Generated by {escape(product_name)}</div>
        <div>Export timestamp: {escape(context["export_timestamp_label"])}</div>
      </div>
    </div>
  </body>
</html>"""
