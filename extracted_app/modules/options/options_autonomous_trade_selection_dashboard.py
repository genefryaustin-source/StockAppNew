"""
Sprint 12 Phase 2 — Autonomous Trade Selection Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_autonomous_trade_selection import (
    DEFAULT_TRADE_SELECTION_POLICY,
    build_autonomous_trade_selection_report,
    generate_trade_selection_playbook,
    summarize_autonomous_trade_selection,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_autonomous_trade_selection_dashboard(
    ticker: str = "",
    paper: bool = True,
    candidates: list[dict[str, Any]] | pd.DataFrame | None = None,
    portfolio_value: float = 100000.0,
    portfolio_optimization_report: dict[str, Any] | None = None,
    csp_report: dict[str, Any] | None = None,
    covered_call_report: dict[str, Any] | None = None,
    wheel_report: dict[str, Any] | None = None,
    income_command_report: dict[str, Any] | None = None,
    volatility_command_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader("🤖 Autonomous Trade Selection")
    st.caption("Candidate ranking · autonomous approval · portfolio-fit scoring · trade-selection playbook")

    with st.expander("Trade Selection Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        min_trade_score = c1.number_input(
            "Minimum Trade Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_TRADE_SELECTION_POLICY["min_trade_score"]),
            step=5.0,
            key="auto_trade_min_trade_score",
        )

        approval_score = c2.number_input(
            "Approval Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_TRADE_SELECTION_POLICY["approval_score"]),
            step=5.0,
            key="auto_trade_approval_score",
        )

        max_capital = c3.number_input(
            "Max Capital Per Trade %",
            min_value=0.1,
            max_value=100.0,
            value=float(DEFAULT_TRADE_SELECTION_POLICY["max_capital_per_trade_pct"]),
            step=1.0,
            key="auto_trade_max_capital_pct",
        )

        d1, d2, d3 = st.columns(3)

        min_liquidity = d1.number_input(
            "Min Liquidity Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_TRADE_SELECTION_POLICY["min_liquidity_score"]),
            step=5.0,
            key="auto_trade_min_liquidity",
        )

        max_assignment = d2.number_input(
            "Max Assignment Probability %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_TRADE_SELECTION_POLICY["max_assignment_probability"]),
            step=1.0,
            key="auto_trade_max_assignment",
        )

        portfolio_value_input = d3.number_input(
            "Portfolio Value",
            min_value=1.0,
            value=float(portfolio_value),
            step=1000.0,
            key="auto_trade_portfolio_value",
        )

    policy = dict(DEFAULT_TRADE_SELECTION_POLICY)
    policy.update({
        "min_trade_score": float(min_trade_score),
        "approval_score": float(approval_score),
        "max_capital_per_trade_pct": float(max_capital),
        "min_liquidity_score": float(min_liquidity),
        "max_assignment_probability": float(max_assignment),
    })

    refresh = st.button(
        "Refresh Autonomous Trade Selection",
        key="autonomous_trade_selection_refresh",
        use_container_width=True,
    )

    cache_key = f"autonomous_trade_selection_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building autonomous trade selection report…"):
            report = build_autonomous_trade_selection_report(
                candidates=candidates,
                portfolio_value=float(portfolio_value_input),
                portfolio_optimization_report=portfolio_optimization_report,
                csp_report=csp_report,
                covered_call_report=covered_call_report,
                wheel_report=wheel_report,
                income_command_report=income_command_report,
                volatility_command_report=volatility_command_report,
                market_maker_report=market_maker_report,
                policy=policy,
            )

            report["playbook"] = generate_trade_selection_playbook(report)
            st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No autonomous trade selection data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", summary.get("candidate_count", 0))
    c2.metric("Approved", summary.get("approved_count", 0))
    c3.metric("Watchlist", summary.get("watchlist_count", 0))
    c4.metric("Top Score", f"{summary.get('top_trade_score', 0)}/100")

    d1, d2, d3 = st.columns(3)
    d1.metric("Avg Score", f"{summary.get('avg_trade_score', 0)}/100")
    d2.metric("Top Decision", summary.get("top_decision", "—"))
    d3.metric("Top Strategy", summary.get("top_strategy", "—"))

    st.markdown("#### Autonomous Trade Selection Summary")
    st.info(summarize_autonomous_trade_selection(report))

    tab_approved, tab_watchlist, tab_all, tab_rejected, tab_playbook = st.tabs(
        [
            "Approved",
            "Watchlist",
            "All Ranked",
            "Rejected",
            "Playbook",
        ]
    )

    cols = [
        "Source",
        "underlying",
        "option_symbol",
        "strategy",
        "trade_type",
        "side",
        "expiry",
        "dte",
        "strike",
        "required_capital",
        "annualized_yield",
        "assignment_probability",
        "liquidity_score",
        "opportunity_score",
        "Trade Score",
        "Decision",
        "Priority",
        "Capital %",
        "Trade Flags",
    ]

    with tab_approved:
        _table(report.get("approved"), cols)

    with tab_watchlist:
        _table(report.get("watchlist"), cols)

    with tab_all:
        _table(report.get("ranked_candidates"), cols)

    with tab_rejected:
        _table(report.get("rejected"), cols)

    with tab_playbook:
        _table((report.get("playbook", {}) or {}).get("playbook"))

    return report
