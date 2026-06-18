"""
Sprint 8 Phase 1 — Position Lifecycle Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_position_lifecycle_engine import (
    DEFAULT_LIFECYCLE_POLICY,
    build_position_lifecycle_report,
    summarize_position_lifecycle,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_position_lifecycle_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🔄 Position Lifecycle Intelligence")
    st.caption("Hold · Trim · Take Profit · Roll · Close · Hedge · Assignment/expiration monitoring")

    with st.expander("Lifecycle Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        profit_take_pct = c1.number_input(
            "Profit Take %",
            min_value=1.0,
            max_value=500.0,
            value=float(DEFAULT_LIFECYCLE_POLICY["profit_take_pct"]),
            step=5.0,
            key="lifecycle_profit_take_pct",
        )

        trim_profit_pct = c2.number_input(
            "Trim Profit %",
            min_value=1.0,
            max_value=500.0,
            value=float(DEFAULT_LIFECYCLE_POLICY["trim_profit_pct"]),
            step=5.0,
            key="lifecycle_trim_profit_pct",
        )

        stop_loss_pct = c3.number_input(
            "Stop Loss %",
            min_value=-500.0,
            max_value=-1.0,
            value=float(DEFAULT_LIFECYCLE_POLICY["stop_loss_pct"]),
            step=5.0,
            key="lifecycle_stop_loss_pct",
        )

        d1, d2, d3 = st.columns(3)

        roll_dte = d1.number_input(
            "Roll DTE",
            min_value=1,
            max_value=120,
            value=int(DEFAULT_LIFECYCLE_POLICY["roll_dte"]),
            step=1,
            key="lifecycle_roll_dte",
        )

        expiration_warning_dte = d2.number_input(
            "Expiration Warning DTE",
            min_value=0,
            max_value=30,
            value=int(DEFAULT_LIFECYCLE_POLICY["expiration_warning_dte"]),
            step=1,
            key="lifecycle_expiration_warning_dte",
        )

        assignment_risk_dte = d3.number_input(
            "Assignment Risk DTE",
            min_value=0,
            max_value=30,
            value=int(DEFAULT_LIFECYCLE_POLICY["assignment_risk_dte"]),
            step=1,
            key="lifecycle_assignment_risk_dte",
        )

    policy = dict(DEFAULT_LIFECYCLE_POLICY)
    policy.update({
        "profit_take_pct": float(profit_take_pct),
        "trim_profit_pct": float(trim_profit_pct),
        "stop_loss_pct": float(stop_loss_pct),
        "roll_dte": int(roll_dte),
        "expiration_warning_dte": int(expiration_warning_dte),
        "assignment_risk_dte": int(assignment_risk_dte),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_position_lifecycle_report(
        positions=positions,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No lifecycle data available."))
        return report

    summary = report.get("summary", {})
    queue = report.get("action_queue", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lifecycle Status", summary.get("portfolio_lifecycle_status", "—"))
    c2.metric("Avg Health", f"{summary.get('avg_health_score', 0)}/100")
    c3.metric("Actions Required", summary.get("action_required_count", 0))
    c4.metric("Critical / High", f"{summary.get('critical_count', 0)} / {summary.get('high_urgency_count', 0)}")

    st.markdown("#### Lifecycle Summary")
    st.info(summarize_position_lifecycle(report))

    tab_queue, tab_positions, tab_actions, tab_urgency = st.tabs(
        [
            "Action Queue",
            "All Positions",
            "Action Counts",
            "Urgency Counts",
        ]
    )

    with tab_queue:
        _table(queue.get("action_queue"))

    with tab_positions:
        positions_df = report.get("positions")
        show_cols = [
            "underlying",
            "option_symbol",
            "option_type",
            "strategy",
            "expiry",
            "dte",
            "strike",
            "qty",
            "market_value",
            "unrealized_pnl",
            "pnl_pct",
            "delta",
            "gamma",
            "theta",
            "vega",
            "Position Health Score",
            "Position Health",
            "Urgency",
            "Recommended Action",
            "Lifecycle Flags",
        ]
        _table(positions_df, show_cols)

    with tab_actions:
        _table(report.get("action_counts"))

    with tab_urgency:
        _table(report.get("urgency_counts"))

    return report
