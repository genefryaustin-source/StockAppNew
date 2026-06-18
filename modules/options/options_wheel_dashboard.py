"""
Sprint 9 Phase 2 — Wheel Strategy Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_wheel_engine import (
    DEFAULT_WHEEL_POLICY,
    build_wheel_command_report,
    summarize_wheel_command,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_wheel_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🛞 Wheel Strategy Command Center")
    st.caption("Cash-secured puts · Assignment transition · Covered calls · Wheel yield · Action queue")

    with st.expander("Wheel Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        min_yield = c1.number_input(
            "Minimum Annualized Yield %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_WHEEL_POLICY["min_annualized_yield"]),
            step=0.5,
            key="wheel_min_yield",
        )

        roll_dte = c2.number_input(
            "Roll DTE",
            min_value=1,
            max_value=120,
            value=int(DEFAULT_WHEEL_POLICY["roll_dte"]),
            step=1,
            key="wheel_roll_dte",
        )

        assignment_dte = c3.number_input(
            "Assignment Warning DTE",
            min_value=0,
            max_value=45,
            value=int(DEFAULT_WHEEL_POLICY["assignment_warning_dte"]),
            step=1,
            key="wheel_assignment_warning_dte",
        )

        d1, d2, d3 = st.columns(3)

        put_delta_min = d1.number_input(
            "Put Delta Min",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_WHEEL_POLICY["target_put_delta_min"]),
            step=0.05,
            key="wheel_put_delta_min",
        )

        put_delta_max = d2.number_input(
            "Put Delta Max",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_WHEEL_POLICY["target_put_delta_max"]),
            step=0.05,
            key="wheel_put_delta_max",
        )

        profit_take = d3.number_input(
            "Profit Take %",
            min_value=1.0,
            max_value=500.0,
            value=float(DEFAULT_WHEEL_POLICY["profit_take_pct"]),
            step=5.0,
            key="wheel_profit_take",
        )

    policy = dict(DEFAULT_WHEEL_POLICY)
    policy.update({
        "min_annualized_yield": float(min_yield),
        "roll_dte": int(roll_dte),
        "assignment_warning_dte": int(assignment_dte),
        "target_put_delta_min": float(put_delta_min),
        "target_put_delta_max": float(put_delta_max),
        "profit_take_pct": float(profit_take),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_wheel_command_report(
        positions=positions,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No wheel strategy data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Wheel Positions", summary.get("wheel_position_count", 0))
    c2.metric("CSPs", summary.get("cash_secured_put_count", 0))
    c3.metric("Covered Calls", summary.get("covered_call_count", 0))
    c4.metric("Queued Actions", summary.get("wheel_action_count", 0))

    d1, d2, d3 = st.columns(3)
    d1.metric("Assigned Stock", summary.get("assigned_stock_count", 0))
    d2.metric("Avg Wheel Score", f"{summary.get('avg_wheel_score', 0)}/100")
    d3.metric("Avg Annualized Yield", f"{summary.get('avg_annualized_yield', 0)}%")

    st.markdown("#### Wheel Summary")
    st.info(summarize_wheel_command(report))

    tab_queue, tab_positions, tab_stage, tab_policy = st.tabs(
        [
            "Wheel Action Queue",
            "Wheel Positions",
            "By Stage",
            "Policy",
        ]
    )

    show_cols = [
        "underlying",
        "option_symbol",
        "Wheel Stage",
        "Recommended Wheel Action",
        "Wheel Score",
        "Wheel Quality",
        "Annualized Wheel Yield",
        "strategy",
        "option_type",
        "expiry",
        "dte",
        "strike",
        "qty",
        "delta",
        "iv",
        "pnl_pct",
        "Wheel Flags",
    ]

    with tab_queue:
        _table(report.get("action_queue"), show_cols)

    with tab_positions:
        _table(report.get("wheel_positions"), show_cols)

    with tab_stage:
        _table(report.get("by_stage", {}).get("by_stage"))

    with tab_policy:
        st.json(report.get("policy", {}))

    return report
