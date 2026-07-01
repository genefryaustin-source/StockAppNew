
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
from modules.forex.ui.forex_optimizer_summary import (
    extract_allocation_rows,
    allocation_table,
    optimizer_commentary,
    optimizer_metrics,
    safe_float,
)
from modules.forex.ui.forex_optimizer_cards import render_optimizer_kpi_ribbon
from modules.forex.ui.forex_optimizer_charts import (
    render_allocation_donut,
    render_risk_budget_bar,
    render_return_risk_scatter,
    render_correlation_heatmap,
    render_optimizer_timeline,
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

def render_forex_portfolio_optimizer_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    rows = extract_allocation_rows(payload)
    metrics = optimizer_metrics(payload, rows)

    if st is None:
        return {"status": "READY", "rows": rows, "metrics": metrics}

    inject_forex_ui_theme(st)
    render_section_header(
        "Portfolio Optimizer Workstation",
        kicker="Institutional Allocation",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_optimizer_kpi_ribbon(payload, rows)

    top = rows[0] if rows else {}
    with panel("Optimizer Decision Banner", kicker="Target Portfolio", meta=metrics.get("optimizer_status", "READY")):
        c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
        c1.markdown(f"## Top Allocation: {top.get('pair', 'EUR/USD')}")
        c2.metric("Weight", f"{safe_float(top.get('weight')):.1f}%")
        c3.metric("Risk Budget", f"{safe_float(top.get('risk_budget')):.1f}%")
        c4.metric("Sharpe", f"{safe_float(top.get('sharpe')):.2f}")
        render_status_pill(metrics.get("optimizer_status", "READY"), label="Optimizer Ready")

    left, right = st.columns([1.35, 1])

    with left:
        with panel("Recommended Allocation", kicker="Target Weights"):
            _table(allocation_table(rows), height=410)

        with panel("Optimizer Narrative", kicker="AI Allocation Summary"):
            st.markdown(optimizer_commentary(payload, rows))

        with panel("Optimizer Timeline", kicker="Allocation Path"):
            render_optimizer_timeline(rows)

    with right:
        with panel("Allocation Donut", kicker="Capital Weights"):
            render_allocation_donut(rows)

        with panel("Risk Budget", kicker="Risk Allocation"):
            render_risk_budget_bar(rows)

        with panel("Return / Risk Map", kicker="Efficient Allocation"):
            render_return_risk_scatter(rows)

    with panel("Correlation Matrix", kicker="Diversification"):
        render_correlation_heatmap(rows)

    with panel("Risk Controls", kicker="Institutional Guardrails"):
        controls = [
            {"Control": "Max Position", "Value": f"{metrics.get('max_position', 0):.1f}%", "Status": "READY" if metrics.get("max_position", 0) <= 30 else "WARNING"},
            {"Control": "Total Deployment", "Value": f"{metrics.get('total_weight', 0):.1f}%", "Status": "READY"},
            {"Control": "Diversification", "Value": f"{metrics.get('diversification_score', 0):.0f}", "Status": "READY" if metrics.get("diversification_score", 0) >= 65 else "WATCH"},
            {"Control": "Execution Mode", "Value": "Paper Trading", "Status": "READY"},
            {"Control": "Live Broker", "Value": "Disabled", "Status": "DISABLED"},
        ]
        _table(controls, height=260)

    return {"status": "READY", "rows": rows, "metrics": metrics}
