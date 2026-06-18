"""
Sprint 6 Phase 4 — Capital Allocation Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_capital_allocation_engine import (
    build_capital_allocation_report,
    summarize_capital_allocation,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def _sample_opportunities() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "SPY",
            "strategy": "Iron Condor",
            "strategy_bucket": "Income",
            "conviction": 72,
            "expected_return": 8,
            "probability_of_profit": 68,
            "risk_reward": 1.4,
            "liquidity_score": 88,
            "greeks_risk_score": 42,
            "capital_required": 2500,
            "recommended_contracts": 2,
        },
        {
            "ticker": "QQQ",
            "strategy": "Bull Call Spread",
            "strategy_bucket": "Directional",
            "conviction": 78,
            "expected_return": 14,
            "probability_of_profit": 55,
            "risk_reward": 2.1,
            "liquidity_score": 84,
            "greeks_risk_score": 55,
            "capital_required": 1800,
            "recommended_contracts": 3,
        },
        {
            "ticker": "NVDA",
            "strategy": "Calendar Spread",
            "strategy_bucket": "Volatility",
            "conviction": 66,
            "expected_return": 18,
            "probability_of_profit": 48,
            "risk_reward": 2.8,
            "liquidity_score": 76,
            "greeks_risk_score": 62,
            "capital_required": 3200,
            "recommended_contracts": 2,
        },
        {
            "ticker": "SPY",
            "strategy": "Protective Put",
            "strategy_bucket": "Hedge",
            "conviction": 60,
            "expected_return": -2,
            "probability_of_profit": 35,
            "risk_reward": 0.8,
            "liquidity_score": 90,
            "greeks_risk_score": 20,
            "capital_required": 1200,
            "recommended_contracts": 1,
        },
    ]


def render_capital_allocation_dashboard(
    opportunities: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("💼 Capital Allocation Intelligence")
    st.caption("Sleeve allocation · Risk budget deployment · Opportunity funding · Capital efficiency")

    with st.expander("Allocation Inputs", expanded=True):
        c1, c2, c3 = st.columns(3)

        portfolio_value = c1.number_input(
            "Portfolio Value ($)",
            min_value=1000.0,
            value=100000.0,
            step=1000.0,
            key="capital_allocation_portfolio_value",
        )

        cash_buffer_pct = c2.number_input(
            "Cash Buffer %",
            min_value=0.0,
            max_value=75.0,
            value=10.0,
            step=1.0,
            key="capital_allocation_cash_buffer",
        ) / 100.0

        max_single_trade_pct = c3.number_input(
            "Max Single Trade %",
            min_value=0.5,
            max_value=25.0,
            value=5.0,
            step=0.5,
            key="capital_allocation_max_single_trade",
        ) / 100.0

    with st.expander("Sleeve Targets", expanded=False):
        s1, s2, s3, s4, s5 = st.columns(5)

        income = s1.number_input("Income %", min_value=0.0, max_value=100.0, value=35.0, step=5.0, key="alloc_income") / 100
        directional = s2.number_input("Directional %", min_value=0.0, max_value=100.0, value=30.0, step=5.0, key="alloc_directional") / 100
        volatility = s3.number_input("Volatility %", min_value=0.0, max_value=100.0, value=20.0, step=5.0, key="alloc_volatility") / 100
        hedge = s4.number_input("Hedge %", min_value=0.0, max_value=100.0, value=10.0, step=5.0, key="alloc_hedge") / 100
        opportunistic = s5.number_input("Opportunistic %", min_value=0.0, max_value=100.0, value=5.0, step=5.0, key="alloc_opportunistic") / 100

    sleeve_targets = {
        "Income": income,
        "Directional": directional,
        "Volatility": volatility,
        "Hedge": hedge,
        "Opportunistic": opportunistic,
    }

    total_target = sum(sleeve_targets.values())
    if abs(total_target - 1.0) > 0.01:
        st.warning(f"Sleeve targets total {total_target * 100:.1f}%. Normalize to 100% for best results.")

    if opportunities is None:
        st.info("Using sample opportunities until Strategy Factory output is wired into this dashboard.")
        opportunities = _sample_opportunities()

    report = build_capital_allocation_report(
        portfolio_value=portfolio_value,
        opportunities=opportunities,
        sleeve_targets=sleeve_targets,
        cash_buffer_pct=cash_buffer_pct,
        max_single_trade_pct=max_single_trade_pct,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No capital allocation data available."))
        return report

    efficiency = report.get("efficiency", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Efficiency Level", efficiency.get("capital_efficiency_level", "—"))
    c2.metric("Efficiency Score", f"{efficiency.get('capital_efficiency_score', 0)}/100")
    c3.metric("Total Allocated", f"${efficiency.get('total_allocated', 0):,.0f}")
    c4.metric("Utilization", f"{efficiency.get('portfolio_utilization_pct', 0)}%")

    st.markdown("#### Allocation Summary")
    st.info(summarize_capital_allocation(report))

    issues = efficiency.get("issues", [])
    if issues:
        st.markdown("#### Capital Allocation Diagnostics")
        for issue in issues:
            st.markdown(f"- {issue}")

    tab_alloc, tab_sleeves, tab_remaining, tab_opps, tab_efficiency = st.tabs(
        [
            "Allocations",
            "Sleeves",
            "Remaining Budget",
            "Scored Opportunities",
            "Efficiency",
        ]
    )

    with tab_alloc:
        _table(report.get("allocations"))

    with tab_sleeves:
        _table(report.get("sleeves"))

    with tab_remaining:
        _table(report.get("remaining"))

    with tab_opps:
        _table(report.get("scored_opportunities"))

    with tab_efficiency:
        st.json(efficiency)

    return report
