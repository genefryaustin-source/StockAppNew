
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    import streamlit as st
    import pandas as pd
except Exception:
    st = None
    pd = None

from modules.forex.ui.forex_ui_theme import inject_forex_ui_theme
from modules.forex.ui.forex_ui_layout import panel, render_section_header
from modules.forex.ui.forex_ui_status import render_status_pill
from modules.forex.ui.forex_enterprise_reports_summary import (
    extract_report_rows,
    report_table,
    report_commentary,
    report_metrics,
    safe_float,
)
from modules.forex.ui.forex_enterprise_reports_cards import render_enterprise_reports_kpi_ribbon
from modules.forex.ui.forex_enterprise_reports_charts import (
    render_report_status_mix,
    render_report_readiness_bar,
    render_report_type_bar,
    render_report_timeline,
)

def _table(rows, height=320):
    if st is None:
        return rows
    if pd is None:
        st.write(rows)
        return
    df = pd.DataFrame(rows if isinstance(rows, list) else [rows])
    if df.empty:
        st.info("No rows available.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)

def render_forex_enterprise_reports_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    rows = extract_report_rows(payload)
    metrics = report_metrics(rows)

    if st is None:
        return {"status": "READY", "rows": rows, "metrics": metrics}

    inject_forex_ui_theme(st)
    render_section_header(
        "Enterprise Reporting Center",
        kicker="Institutional Reports",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_enterprise_reports_kpi_ribbon(rows)

    top = rows[0] if rows else {}
    with panel("Reporting Control Banner", kicker="Executive Reporting", meta=metrics.get("readiness", 0)):
        c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
        c1.markdown(f"## {top.get('report', 'Daily AI Brief')}")
        c2.metric("Status", top.get("status", "READY"))
        c3.metric("Readiness", f"{safe_float(top.get('readiness')):.0f}%")
        c4.metric("Format", top.get("format", "PDF"))
        render_status_pill(top.get("status", "READY"), label="Report Center")

    left, right = st.columns([1.35, 1])

    with left:
        with panel("Enterprise Report Catalog", kicker="Reports"):
            _table(report_table(rows), height=420)

        with panel("Reporting Narrative", kicker="Executive Summary"):
            st.markdown(report_commentary(rows))

        with panel("Reporting Timeline", kicker="Readiness"):
            render_report_timeline(rows)

    with right:
        with panel("Report Status Mix", kicker="Status"):
            render_report_status_mix(rows)

        with panel("Readiness by Report", kicker="Completion"):
            render_report_readiness_bar(rows)

        with panel("Report Type Coverage", kicker="Coverage"):
            render_report_type_bar(rows)

    with panel("Report Actions", kicker="Generate / Preview / Export"):
        actions = []
        for row in rows:
            actions.append({
                "Report": row.get("report"),
                "Preview": "Available" if row.get("status") in {"READY", "GENERATED", "COMPLETE", "COMPLETED"} else "Pending",
                "Generate": "Enabled",
                "Export": row.get("format", "PDF"),
                "Audience": row.get("audience"),
            })
        _table(actions, height=300)

    with panel("Governance & Distribution", kicker="Controls"):
        controls = [
            {"Control": "Raw JSON Visibility", "Current": "Developer Tab Only", "Status": "PASS"},
            {"Control": "Executive Report Pack", "Current": "Ready", "Status": "READY"},
            {"Control": "Risk Report", "Current": "Queued / Scheduled", "Status": "WATCH"},
            {"Control": "Model Audit Trail", "Current": "Available", "Status": "READY"},
            {"Control": "Export Safety", "Current": "Local / Paper Trading", "Status": "READY"},
        ]
        _table(controls, height=260)

    return {"status": "READY", "rows": rows, "metrics": metrics}
