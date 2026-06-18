"""
Sprint 12 Phase 1 — Portfolio Optimization AI Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_optimization_ai import (
    DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY,
    build_portfolio_optimization_report,
    summarize_portfolio_optimization,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_portfolio_optimization_ai_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
    risk_report: dict[str, Any] | None = None,
    construction_report: dict[str, Any] | None = None,
    income_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader("🧠 Portfolio Optimization AI")
    st.caption("Autonomous Options CIO · objective scoring · position optimization · allocation recommendations")

    with st.expander("Optimization Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        target_health = c1.number_input(
            "Target Health Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["target_health_score"]),
            step=5,
            key="opt_ai_target_health_score",
        )

        max_single = c2.number_input(
            "Max Single Position %",
            min_value=1.0,
            max_value=100.0,
            value=float(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["max_single_position_pct"]),
            step=1.0,
            key="opt_ai_max_single_position_pct",
        )

        max_symbol = c3.number_input(
            "Max Symbol Exposure %",
            min_value=1.0,
            max_value=100.0,
            value=float(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["max_symbol_exposure_pct"]),
            step=1.0,
            key="opt_ai_max_symbol_exposure_pct",
        )

        d1, d2, d3 = st.columns(3)

        min_liquidity = d1.number_input(
            "Min Liquidity Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["min_liquidity_score"]),
            step=5,
            key="opt_ai_min_liquidity_score",
        )

        target_cash = d2.number_input(
            "Target Cash %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["target_cash_pct"]),
            step=1.0,
            key="opt_ai_target_cash_pct",
        )

        max_short_gamma = d3.number_input(
            "Max Short Gamma Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY["max_short_gamma_score"]),
            step=5.0,
            key="opt_ai_max_short_gamma_score",
        )

    policy = dict(DEFAULT_PORTFOLIO_OPTIMIZATION_POLICY)
    policy.update({
        "target_health_score": float(target_health),
        "max_single_position_pct": float(max_single),
        "max_symbol_exposure_pct": float(max_symbol),
        "min_liquidity_score": float(min_liquidity),
        "target_cash_pct": float(target_cash),
        "max_short_gamma_score": float(max_short_gamma),
    })

    refresh = st.button(
        "Refresh Portfolio Optimization AI",
        key="portfolio_optimization_ai_refresh",
        use_container_width=True,
    )

    cache_key = f"portfolio_optimization_ai_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building portfolio optimization AI report…"):
            if positions is None:
                positions = load_portfolio_positions(ticker=ticker, paper=paper)

            report = build_portfolio_optimization_report(
                positions=positions,
                risk_report=risk_report,
                construction_report=construction_report,
                income_report=income_report,
                liquidity_report=liquidity_report,
                market_maker_report=market_maker_report,
                volatility_report=volatility_report,
                policy=policy,
            )

            st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No portfolio optimization data available."))
        return report

    summary = report.get("summary", {})
    objective = report.get("objective", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Objective Rating", summary.get("objective_rating", "—"))
    c2.metric("Objective Score", f"{summary.get('objective_score', 0)}/100")
    c3.metric("Actions", summary.get("optimization_action_count", 0))
    c4.metric("Top Playbook", summary.get("top_playbook", "—"))

    d1, d2, d3 = st.columns(3)
    d1.metric("Largest Position", f"{summary.get('largest_position_pct', 0)}%")
    d2.metric("Symbols", summary.get("symbol_count", 0))
    d3.metric("Market Penalty", objective.get("market_condition_penalty", 0))

    st.markdown("#### Optimization Summary")
    st.info(summarize_portfolio_optimization(report))

    drivers = objective.get("drivers", [])
    if drivers:
        st.markdown("#### Optimization Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_actions, tab_allocation, tab_exposure, tab_score, tab_playbook = st.tabs(
        [
            "Action Queue",
            "Allocation",
            "Exposure Map",
            "Objective Components",
            "Playbook",
        ]
    )

    with tab_actions:
        _table((report.get("actions", {}) or {}).get("action_queue"))

    with tab_allocation:
        _table((report.get("allocation", {}) or {}).get("allocation_recommendations"))

    with tab_exposure:
        _table((report.get("actions", {}) or {}).get("by_symbol"))

    with tab_score:
        component_rows = pd.DataFrame([
            {"Component": "Risk", "Score": objective.get("risk_component", 0)},
            {"Component": "Construction", "Score": objective.get("construction_component", 0)},
            {"Component": "Income", "Score": objective.get("income_component", 0)},
            {"Component": "Liquidity", "Score": objective.get("liquidity_component", 0)},
            {"Component": "Market Penalty", "Score": objective.get("market_condition_penalty", 0)},
        ])
        _table(component_rows)

    with tab_playbook:
        _table((report.get("playbook", {}) or {}).get("playbook"))

    return report
