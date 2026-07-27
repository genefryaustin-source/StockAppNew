"""
Sprint 8 Phase 2 — Rolling Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_roll_engine import (
    DEFAULT_ROLL_POLICY,
    build_rolling_intelligence_report,
    summarize_rolling_intelligence,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_roll_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🔁 Rolling Intelligence")
    st.caption("Roll queue · DTE monitoring · credit/debit estimates · roll guidance")

    with st.expander("Roll Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        roll_dte = c1.number_input(
            "Roll DTE",
            min_value=1,
            max_value=120,
            value=int(DEFAULT_ROLL_POLICY["roll_dte"]),
            step=1,
            key="roll_policy_roll_dte",
        )

        urgent_roll_dte = c2.number_input(
            "Urgent Roll DTE",
            min_value=0,
            max_value=30,
            value=int(DEFAULT_ROLL_POLICY["urgent_roll_dte"]),
            step=1,
            key="roll_policy_urgent_roll_dte",
        )

        profit_roll_pct = c3.number_input(
            "Profit Roll %",
            min_value=1.0,
            max_value=500.0,
            value=float(DEFAULT_ROLL_POLICY["profit_roll_pct"]),
            step=5.0,
            key="roll_policy_profit_roll_pct",
        )

        d1, d2, d3 = st.columns(3)

        loss_roll_pct = d1.number_input(
            "Loss Roll %",
            min_value=-500.0,
            max_value=-1.0,
            value=float(DEFAULT_ROLL_POLICY["loss_roll_pct"]),
            step=5.0,
            key="roll_policy_loss_roll_pct",
        )

        high_delta = d2.number_input(
            "High Delta Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_ROLL_POLICY["high_delta_threshold"]),
            step=0.05,
            key="roll_policy_high_delta",
        )

        assignment_dte = d3.number_input(
            "Assignment Risk DTE",
            min_value=0,
            max_value=30,
            value=int(DEFAULT_ROLL_POLICY["assignment_risk_dte"]),
            step=1,
            key="roll_policy_assignment_dte",
        )

    policy = dict(DEFAULT_ROLL_POLICY)
    policy.update({
        "roll_dte": int(roll_dte),
        "urgent_roll_dte": int(urgent_roll_dte),
        "profit_roll_pct": float(profit_roll_pct),
        "loss_roll_pct": float(loss_roll_pct),
        "high_delta_threshold": float(high_delta),
        "assignment_risk_dte": int(assignment_dte),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_rolling_intelligence_report(positions=positions, policy=policy)

    if not report.get("available"):
        st.info(report.get("reason", "No rolling intelligence data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Roll Candidates", summary.get("roll_candidate_count", 0))
    c2.metric("Critical", summary.get("critical_count", 0))
    c3.metric("High Urgency", summary.get("high_count", 0))
    c4.metric("Avg Roll Score", f"{summary.get('avg_roll_score', 0)}/100")

    st.markdown("#### Rolling Summary")
    st.info(summarize_rolling_intelligence(report))

    tab_queue, tab_positions, tab_type = st.tabs(["Roll Queue", "All Positions", "By Roll Type"])

    show_cols = [
        "underlying", "option_symbol", "option_type", "strategy", "expiry", "dte",
        "strike", "qty", "pnl_pct", "delta", "gamma", "theta", "Roll Type",
        "Roll Score", "Roll Urgency", "Roll Decision", "Roll Direction",
        "Target DTE Window", "Suggested Strike", "Estimated Net Credit/Debit",
        "Credit/Debit", "Roll Flags", "Guidance",
    ]

    with tab_queue:
        _table(report.get("roll_queue"), show_cols)

    with tab_positions:
        _table(report.get("positions"), show_cols)

    with tab_type:
        _table(report.get("by_roll_type", {}).get("by_roll_type"))

    return report
