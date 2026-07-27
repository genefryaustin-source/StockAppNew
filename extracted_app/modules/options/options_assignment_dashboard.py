"""
Sprint 8 Phase 4 — Assignment & Expiration Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_assignment_engine import (
    DEFAULT_ASSIGNMENT_POLICY,
    build_assignment_expiration_report,
    summarize_assignment_expiration,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_assignment_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("⏳ Assignment & Expiration Intelligence")
    st.caption("Assignment risk · Expiration risk · Pin risk · Early exercise risk · ITM short monitoring")

    with st.expander("Assignment / Expiration Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        expiration_warning_dte = c1.number_input(
            "Expiration Warning DTE",
            min_value=0,
            max_value=45,
            value=int(DEFAULT_ASSIGNMENT_POLICY["expiration_warning_dte"]),
            step=1,
            key="assignment_expiration_warning_dte",
        )

        critical_expiration_dte = c2.number_input(
            "Critical Expiration DTE",
            min_value=0,
            max_value=14,
            value=int(DEFAULT_ASSIGNMENT_POLICY["critical_expiration_dte"]),
            step=1,
            key="assignment_critical_expiration_dte",
        )

        assignment_risk_dte = c3.number_input(
            "Assignment Risk DTE",
            min_value=0,
            max_value=45,
            value=int(DEFAULT_ASSIGNMENT_POLICY["assignment_risk_dte"]),
            step=1,
            key="assignment_assignment_risk_dte",
        )

        d1, d2, d3 = st.columns(3)

        high_delta = d1.number_input(
            "High Delta Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_ASSIGNMENT_POLICY["high_delta_threshold"]),
            step=0.05,
            key="assignment_high_delta_threshold",
        )

        very_high_delta = d2.number_input(
            "Very High Delta Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_ASSIGNMENT_POLICY["very_high_delta_threshold"]),
            step=0.05,
            key="assignment_very_high_delta_threshold",
        )

        pin_risk_pct = d3.number_input(
            "Pin Risk % From Strike",
            min_value=0.1,
            max_value=10.0,
            value=float(DEFAULT_ASSIGNMENT_POLICY["pin_risk_pct"]),
            step=0.1,
            key="assignment_pin_risk_pct",
        )

    policy = dict(DEFAULT_ASSIGNMENT_POLICY)
    policy.update({
        "expiration_warning_dte": int(expiration_warning_dte),
        "critical_expiration_dte": int(critical_expiration_dte),
        "assignment_risk_dte": int(assignment_risk_dte),
        "high_delta_threshold": float(high_delta),
        "very_high_delta_threshold": float(very_high_delta),
        "pin_risk_pct": float(pin_risk_pct),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_assignment_expiration_report(
        positions=positions,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No assignment / expiration data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Alerts", summary.get("assignment_alert_count", 0))
    c2.metric("Critical Assignment", summary.get("critical_assignment_count", 0))
    c3.metric("Critical Expiration", summary.get("critical_expiration_count", 0))
    c4.metric("Pin Risk", summary.get("pin_risk_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("ITM Shorts", summary.get("itm_short_count", 0))
    d2.metric("High Assignment", summary.get("high_assignment_count", 0))
    d3.metric("High Expiration", summary.get("high_expiration_count", 0))
    d4.metric("Avg Assign Score", f"{summary.get('avg_assignment_score', 0)}/100")

    st.markdown("#### Assignment & Expiration Summary")
    st.info(summarize_assignment_expiration(report))

    tab_alerts, tab_positions, tab_underlying, tab_policy = st.tabs(
        [
            "Alert Queue",
            "All Positions",
            "By Underlying",
            "Policy",
        ]
    )

    show_cols = [
        "underlying",
        "option_symbol",
        "option_type",
        "strategy",
        "expiry",
        "dte",
        "strike",
        "underlying_price",
        "qty",
        "delta",
        "gamma",
        "theta",
        "Moneyness",
        "Moneyness %",
        "Distance To Strike %",
        "ITM",
        "Assignment Risk",
        "Assignment Risk Score",
        "Expiration Risk",
        "Expiration Risk Score",
        "Recommended Action",
        "Assignment Flags",
        "Expiration Flags",
    ]

    with tab_alerts:
        _table(report.get("alert_queue"), show_cols)

    with tab_positions:
        _table(report.get("positions"), show_cols)

    with tab_underlying:
        _table(report.get("by_underlying", {}).get("by_underlying"))

    with tab_policy:
        st.json(report.get("policy", {}))

    return report
