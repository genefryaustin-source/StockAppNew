"""
Sprint 7 Phase 3 — Institutional Trade Planner Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_institutional_trade_planner_engine import (
    DEFAULT_PLANNER_POLICY,
    build_institutional_trade_plan,
    summarize_institutional_trade_plan,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def _sample_trade_candidates() -> list[dict[str, Any]]:
    return [
        {
            "ticker": "SPY",
            "strategy": "Iron Condor",
            "strategy_bucket": "Income",
            "direction": "Neutral",
            "entry_price": 2.10,
            "target_price": 1.05,
            "stop_price": 3.60,
            "max_loss": 290,
            "max_profit": 210,
            "capital_required": 2900,
            "allocated_capital": 2500,
            "recommended_contracts": 2,
            "optimization_score": 82,
            "recommended_action": "APPROVE",
            "liquidity_score": 88,
            "execution_score": 82,
            "greeks_risk_score": 42,
            "portfolio_risk_score": 48,
            "spread_pct": 0.04,
            "slippage_bps": 35,
            "probability_of_profit": 68,
            "risk_reward": 1.4,
            "conviction": 74,
            "dte": 35,
            "expiry": "2026-07-17",
        },
        {
            "ticker": "QQQ",
            "strategy": "Bull Call Spread",
            "strategy_bucket": "Directional",
            "direction": "Bullish",
            "entry_price": 3.25,
            "target_price": 5.50,
            "stop_price": 1.75,
            "max_loss": 325,
            "max_profit": 675,
            "capital_required": 1800,
            "allocated_capital": 1800,
            "recommended_contracts": 3,
            "optimization_score": 76,
            "recommended_action": "APPROVE_SMALL",
            "liquidity_score": 84,
            "execution_score": 78,
            "greeks_risk_score": 55,
            "portfolio_risk_score": 54,
            "spread_pct": 0.06,
            "slippage_bps": 55,
            "probability_of_profit": 55,
            "risk_reward": 2.1,
            "conviction": 82,
            "dte": 42,
            "expiry": "2026-07-24",
        },
        {
            "ticker": "NVDA",
            "strategy": "Calendar Spread",
            "strategy_bucket": "Volatility",
            "direction": "Neutral Vol",
            "entry_price": 4.10,
            "target_price": 6.50,
            "stop_price": 2.40,
            "max_loss": 410,
            "max_profit": 800,
            "capital_required": 3200,
            "allocated_capital": 2500,
            "recommended_contracts": 2,
            "optimization_score": 64,
            "recommended_action": "WATCHLIST",
            "liquidity_score": 70,
            "execution_score": 65,
            "greeks_risk_score": 68,
            "portfolio_risk_score": 62,
            "spread_pct": 0.12,
            "slippage_bps": 110,
            "probability_of_profit": 48,
            "risk_reward": 2.8,
            "conviction": 67,
            "dte": 28,
            "expiry": "2026-07-10",
        },
    ]


def render_institutional_trade_planner_dashboard(
    trade_candidates: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("📋 Institutional Trade Planner")
    st.caption("Trade plan readiness · Entry/exit checklist · Risk controls · Approval decision")

    with st.expander("Planner Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        min_opt = c1.number_input(
            "Min Optimization Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PLANNER_POLICY["min_optimization_score"]),
            step=5,
            key="planner_min_optimization_score",
        )

        min_liq = c2.number_input(
            "Min Liquidity Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PLANNER_POLICY["min_liquidity_score"]),
            step=5,
            key="planner_min_liquidity_score",
        )

        max_greek = c3.number_input(
            "Max Greeks Risk",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PLANNER_POLICY["max_greeks_risk_score"]),
            step=5,
            key="planner_max_greeks_risk",
        )

        d1, d2, d3 = st.columns(3)

        max_port = d1.number_input(
            "Max Portfolio Risk",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_PLANNER_POLICY["max_portfolio_risk_score"]),
            step=5,
            key="planner_max_portfolio_risk",
        )

        max_slip = d2.number_input(
            "Max Slippage bps",
            min_value=0,
            max_value=1000,
            value=int(DEFAULT_PLANNER_POLICY["max_slippage_bps"]),
            step=25,
            key="planner_max_slippage",
        )

        max_spread = d3.number_input(
            "Max Spread %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_PLANNER_POLICY["max_spread_pct"]),
            step=1.0,
            key="planner_max_spread",
        )

    policy = dict(DEFAULT_PLANNER_POLICY)
    policy.update({
        "min_optimization_score": float(min_opt),
        "min_liquidity_score": float(min_liq),
        "max_greeks_risk_score": float(max_greek),
        "max_portfolio_risk_score": float(max_port),
        "max_slippage_bps": float(max_slip),
        "max_spread_pct": float(max_spread),
    })

    if trade_candidates is None:
        st.info("Using sample trade candidates until Trade Optimization output is wired into this planner.")
        trade_candidates = _sample_trade_candidates()

    report = build_institutional_trade_plan(
        trade_candidates=trade_candidates,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No trade planning data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Plans", summary.get("plan_count", 0))
    c2.metric("Approved", summary.get("approved_count", 0))
    c3.metric("Revise", summary.get("revise_count", 0))
    c4.metric("Rejected", summary.get("reject_count", 0))

    st.metric("Avg Readiness", f"{summary.get('avg_readiness_score', 0)}/100")

    st.markdown("#### Planner Summary")
    st.info(summarize_institutional_trade_plan(report))

    tab_summary, tab_checklist, tab_details = st.tabs(
        [
            "Plan Summary",
            "Checklist",
            "Plan Details",
        ]
    )

    with tab_summary:
        _table(report.get("plan_summary"))

    with tab_checklist:
        _table(report.get("checklist"))

    with tab_details:
        plans = report.get("plans", [])
        if plans:
            labels = [
                f"{i + 1}. {p.get('Ticker', '—')} — {p.get('Strategy', '—')} ({p.get('Planner Decision', '—')})"
                for i, p in enumerate(plans)
            ]

            selected = st.selectbox(
                "Trade Plan",
                labels,
                index=0,
                key="institutional_trade_plan_selector",
            )

            idx = labels.index(selected)
            plan = plans[idx]

            st.markdown("##### Entry Plan")
            st.json(plan.get("Entry Plan", {}))

            st.markdown("##### Exit Plan")
            st.json(plan.get("Exit Plan", {}))

            st.markdown("##### Risk Controls")
            st.json(plan.get("Risk Controls", {}))
        else:
            st.caption("No plan details available.")

    return report
