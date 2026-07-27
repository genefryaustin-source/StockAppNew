"""
Sprint 6 Phase 5 — Trade Optimization Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_trade_optimization_engine import (
    DEFAULT_OPTIMIZATION_WEIGHTS,
    build_trade_optimization_report,
    summarize_trade_optimization,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def _sample_candidates() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "SPY",
            "strategy": "Iron Condor",
            "strategy_bucket": "Income",
            "conviction": 74,
            "expected_return": 8,
            "probability_of_profit": 68,
            "risk_reward": 1.4,
            "capital_required": 2500,
            "allocated_capital": 2200,
            "recommended_contracts": 2,
            "liquidity_score": 88,
            "execution_score": 82,
            "greeks_risk_score": 42,
            "portfolio_risk_score": 48,
            "spread_pct": 0.04,
            "slippage_bps": 35,
        },
        {
            "ticker": "QQQ",
            "strategy": "Bull Call Spread",
            "strategy_bucket": "Directional",
            "conviction": 82,
            "expected_return": 14,
            "probability_of_profit": 55,
            "risk_reward": 2.1,
            "capital_required": 1800,
            "allocated_capital": 1800,
            "recommended_contracts": 3,
            "liquidity_score": 84,
            "execution_score": 78,
            "greeks_risk_score": 55,
            "portfolio_risk_score": 54,
            "spread_pct": 0.06,
            "slippage_bps": 55,
        },
        {
            "ticker": "NVDA",
            "strategy": "Calendar Spread",
            "strategy_bucket": "Volatility",
            "conviction": 67,
            "expected_return": 18,
            "probability_of_profit": 48,
            "risk_reward": 2.8,
            "capital_required": 3200,
            "allocated_capital": 2500,
            "recommended_contracts": 2,
            "liquidity_score": 70,
            "execution_score": 65,
            "greeks_risk_score": 68,
            "portfolio_risk_score": 62,
            "spread_pct": 0.12,
            "slippage_bps": 110,
        },
        {
            "ticker": "ILLQ",
            "strategy": "Long Call",
            "strategy_bucket": "Directional",
            "conviction": 61,
            "expected_return": 30,
            "probability_of_profit": 35,
            "risk_reward": 3.5,
            "capital_required": 1000,
            "allocated_capital": 1000,
            "recommended_contracts": 5,
            "liquidity_score": 28,
            "execution_score": 40,
            "greeks_risk_score": 80,
            "portfolio_risk_score": 75,
            "spread_pct": 0.28,
            "slippage_bps": 350,
        },
    ]


def render_trade_optimization_dashboard(
    candidates: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🎯 Trade Optimization Engine")
    st.caption("Candidate ranking · Execution feasibility · Capital efficiency · Risk-adjusted approval")

    with st.expander("Optimization Weights", expanded=False):
        c1, c2, c3 = st.columns(3)
        conviction = c1.number_input(
            "Conviction Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["conviction"]),
            step=0.01,
            key="trade_opt_weight_conviction",
        )
        liquidity = c2.number_input(
            "Liquidity Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["liquidity"]),
            step=0.01,
            key="trade_opt_weight_liquidity",
        )
        risk_reward = c3.number_input(
            "Risk/Reward Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["risk_reward"]),
            step=0.01,
            key="trade_opt_weight_rr",
        )

        d1, d2, d3 = st.columns(3)
        capital_efficiency = d1.number_input(
            "Capital Efficiency Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["capital_efficiency"]),
            step=0.01,
            key="trade_opt_weight_cap_eff",
        )
        execution_quality = d2.number_input(
            "Execution Quality Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["execution_quality"]),
            step=0.01,
            key="trade_opt_weight_exec",
        )
        risk_penalty = d3.number_input(
            "Risk Penalty Weight",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_OPTIMIZATION_WEIGHTS["risk_penalty"]),
            step=0.01,
            key="trade_opt_weight_risk",
        )

    weights = {
        "conviction": conviction,
        "liquidity": liquidity,
        "risk_reward": risk_reward,
        "capital_efficiency": capital_efficiency,
        "execution_quality": execution_quality,
        "risk_penalty": risk_penalty,
    }

    if candidates is None:
        st.info("Using sample candidates until Strategy Factory / Capital Allocation output is wired into this dashboard.")
        candidates = _sample_candidates()

    report = build_trade_optimization_report(candidates, weights=weights)

    if not report.get("available"):
        st.info(report.get("reason", "No optimization data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", summary.get("candidate_count", 0))
    c2.metric("Approved", summary.get("approved_count", 0))
    c3.metric("Watchlist", summary.get("watchlist_count", 0))
    c4.metric("Rejected", summary.get("rejected_count", 0))

    s1, s2, s3 = st.columns(3)
    s1.metric("Average Score", f"{summary.get('avg_optimization_score', 0)}/100")
    s2.metric("Top Candidate", summary.get("top_candidate", "—"))
    s3.metric("Top Score", f"{summary.get('top_score', 0)}/100")

    st.markdown("#### Optimization Summary")
    st.info(summarize_trade_optimization(report))

    tab_top, tab_all, tab_bucket, tab_avoid = st.tabs(
        [
            "Top Trades",
            "All Candidates",
            "By Bucket",
            "Avoid",
        ]
    )

    show_cols = [
        "ticker",
        "strategy",
        "strategy_bucket",
        "conviction",
        "liquidity_score",
        "execution_score",
        "risk_reward",
        "capital_efficiency_score",
        "execution_feasibility_score",
        "execution_difficulty",
        "optimization_score",
        "recommended_action",
        "optimization_priority",
        "routing_guidance",
        "optimization_notes",
    ]

    with tab_top:
        _table(report.get("top_trades"), show_cols)

    with tab_all:
        _table(report.get("candidates"), show_cols)

    with tab_bucket:
        _table(report.get("by_bucket", {}).get("by_bucket"))

    with tab_avoid:
        _table(report.get("avoid_trades"), show_cols)

    return report
