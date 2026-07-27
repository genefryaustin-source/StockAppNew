
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
from modules.forex.ui.forex_execution_algo_summary import (
    extract_execution_rows,
    execution_metrics,
    execution_table,
    execution_commentary,
    safe_float,
)
from modules.forex.ui.forex_execution_algo_cards import render_execution_algo_kpi_ribbon
from modules.forex.ui.forex_execution_algo_charts import (
    render_algo_mix,
    render_slippage_bar,
    render_latency_timeline,
    render_fill_progress,
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

def render_forex_execution_algorithms_workspace(payload: Optional[Dict[str, Any]] = None, *, db=None) -> Dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    rows = extract_execution_rows(payload)
    metrics = execution_metrics(rows)

    if st is None:
        return {"status": "READY", "rows": rows, "metrics": metrics}

    inject_forex_ui_theme(st)
    render_section_header(
        "Execution Algorithms Workstation",
        kicker="TWAP / VWAP / Iceberg / Smart Router",
        meta=datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
    )

    render_execution_algo_kpi_ribbon(rows)

    top = rows[0] if rows else {}
    with panel("Execution Control Banner", kicker="Algorithmic Routing", meta=metrics.get("execution_mode", "PAPER")):
        c1, c2, c3, c4 = st.columns([1.25, 1, 1, 1])
        c1.markdown(f"## {top.get('algorithm', 'SMART')} {top.get('pair', 'EUR/USD')}")
        c2.metric("Target Units", f"{safe_float(top.get('target_units')):,.0f}")
        c3.metric("Fill Rate", f"{safe_float(top.get('fill_rate')):.1f}%")
        c4.metric("Slippage", f"{safe_float(top.get('slippage_bps')):.2f} bps")
        render_status_pill(top.get("status", "READY"), label="Paper Execution")

    left, right = st.columns([1.35, 1])

    with left:
        with panel("Algorithmic Order Blotter", kicker="Routes"):
            _table(execution_table(rows), height=410)

        with panel("Execution Narrative", kicker="Routing Summary"):
            st.markdown(execution_commentary(rows))

        with panel("Fill Progress", kicker="Completion"):
            render_fill_progress(rows)

    with right:
        with panel("Algorithm Mix", kicker="Route Types"):
            render_algo_mix(rows)

        with panel("Expected Slippage", kicker="Execution Cost"):
            render_slippage_bar(rows)

        with panel("Routing Latency", kicker="Infrastructure"):
            render_latency_timeline(rows)

    with panel("Execution Guardrails", kicker="Broker Safety"):
        guardrails = [
            {"Control": "Broker Mode", "Current": metrics.get("execution_mode", "PAPER"), "Status": "DISABLED" if metrics.get("execution_mode") == "PAPER" else "READY"},
            {"Control": "Max Slippage", "Current": f"{metrics.get('avg_slippage_bps', 0):.2f} bps", "Status": "READY" if metrics.get("avg_slippage_bps", 0) <= 1 else "WARNING"},
            {"Control": "Latency", "Current": f"{metrics.get('avg_latency_ms', 0):.0f} ms", "Status": "READY" if metrics.get("avg_latency_ms", 0) <= 150 else "WARNING"},
            {"Control": "Live Routing", "Current": "Disabled", "Status": "DISABLED"},
            {"Control": "Paper Validation", "Current": "Enabled", "Status": "READY"},
        ]
        _table(guardrails, height=260)

    with panel("Algorithm Capabilities", kicker="Available Engines"):
        capabilities = [
            {"Algorithm": "TWAP", "Use Case": "Time-sliced execution", "Status": "READY"},
            {"Algorithm": "VWAP", "Use Case": "Volume-aware execution", "Status": "READY"},
            {"Algorithm": "Iceberg", "Use Case": "Large order concealment", "Status": "READY"},
            {"Algorithm": "Smart Router", "Use Case": "Route selection / provider fallback", "Status": "READY"},
        ]
        _table(capabilities, height=240)

    return {"status": "READY", "rows": rows, "metrics": metrics}
