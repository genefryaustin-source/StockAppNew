"""
Sprint 12 Phase 3 — Autonomous Risk Rebalancing Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_autonomous_risk_rebalancing import (
    DEFAULT_RISK_REBALANCING_POLICY,
    build_autonomous_risk_rebalancing_report,
    summarize_autonomous_risk_rebalancing,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_autonomous_risk_rebalancing_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
    risk_report: dict[str, Any] | None = None,
    greeks_report: dict[str, Any] | None = None,
    guardrails_report: dict[str, Any] | None = None,
    liquidity_report: dict[str, Any] | None = None,
    market_maker_report: dict[str, Any] | None = None,
    volatility_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader("🧭 Autonomous Risk Rebalancing")
    st.caption("Risk triggers · Greek rebalancing · concentration control · liquidity-aware action queue")

    with st.expander("Risk Rebalancing Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        max_risk = c1.number_input(
            "Max Risk Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["max_risk_score"]),
            step=5.0,
            key="risk_rebal_max_risk_score",
        )

        target_risk = c2.number_input(
            "Target Risk Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["target_risk_score"]),
            step=5.0,
            key="risk_rebal_target_risk_score",
        )

        max_symbol = c3.number_input(
            "Max Symbol Exposure %",
            min_value=1.0,
            max_value=100.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["max_single_symbol_pct"]),
            step=1.0,
            key="risk_rebal_max_single_symbol_pct",
        )

        d1, d2, d3 = st.columns(3)

        max_delta = d1.number_input(
            "Max |Delta|",
            min_value=0.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["max_delta_abs"]),
            step=25.0,
            key="risk_rebal_max_delta",
        )

        max_gamma = d2.number_input(
            "Max |Gamma|",
            min_value=0.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["max_gamma_abs"]),
            step=5.0,
            key="risk_rebal_max_gamma",
        )

        max_vega = d3.number_input(
            "Max |Vega|",
            min_value=0.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["max_vega_abs"]),
            step=50.0,
            key="risk_rebal_max_vega",
        )

        e1, e2 = st.columns(2)

        min_liquidity = e1.number_input(
            "Min Liquidity Score",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_RISK_REBALANCING_POLICY["min_liquidity_score"]),
            step=5.0,
            key="risk_rebal_min_liquidity",
        )

        urgent_dte = e2.number_input(
            "Urgent DTE",
            min_value=0,
            max_value=60,
            value=int(DEFAULT_RISK_REBALANCING_POLICY["urgent_dte"]),
            step=1,
            key="risk_rebal_urgent_dte",
        )

    policy = dict(DEFAULT_RISK_REBALANCING_POLICY)
    policy.update({
        "max_risk_score": float(max_risk),
        "target_risk_score": float(target_risk),
        "max_single_symbol_pct": float(max_symbol),
        "max_delta_abs": float(max_delta),
        "max_gamma_abs": float(max_gamma),
        "max_vega_abs": float(max_vega),
        "min_liquidity_score": float(min_liquidity),
        "urgent_dte": int(urgent_dte),
    })

    refresh = st.button(
        "Refresh Autonomous Risk Rebalancing",
        key="autonomous_risk_rebalancing_refresh",
        use_container_width=True,
    )

    cache_key = f"autonomous_risk_rebalancing_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building autonomous risk rebalancing report…"):
            if positions is None:
                positions = load_portfolio_positions(ticker=ticker, paper=paper)

            report = build_autonomous_risk_rebalancing_report(
                positions=positions,
                risk_report=risk_report,
                greeks_report=greeks_report,
                guardrails_report=guardrails_report,
                liquidity_report=liquidity_report,
                market_maker_report=market_maker_report,
                volatility_report=volatility_report,
                policy=policy,
            )

            st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No autonomous risk rebalancing data available."))
        return report

    summary = report.get("summary", {})
    trigger_summary = (report.get("triggers", {}) or {}).get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rebalance Urgency", summary.get("rebalance_urgency", "—"))
    c2.metric("Rebalance Score", f"{summary.get('rebalance_score', 0)}/100")
    c3.metric("Triggers", summary.get("trigger_count", 0))
    c4.metric("Actions", summary.get("action_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Risk Score", trigger_summary.get("risk_score", 0))
    d2.metric("Net Delta", trigger_summary.get("net_delta", 0))
    d3.metric("Net Gamma", trigger_summary.get("net_gamma", 0))
    d4.metric("Largest Symbol", f"{trigger_summary.get('largest_symbol_pct', 0)}%")

    st.markdown("#### Rebalancing Summary")
    st.info(summarize_autonomous_risk_rebalancing(report))

    drivers = (report.get("score", {}) or {}).get("drivers", [])
    if drivers:
        st.markdown("#### Rebalance Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_queue, tab_triggers, tab_symbol, tab_positions, tab_playbook = st.tabs(
        [
            "Rebalance Queue",
            "Triggers",
            "Symbol Exposure",
            "Positions",
            "Playbook",
        ]
    )

    with tab_queue:
        _table((report.get("queue", {}) or {}).get("rebalance_queue"))

    with tab_triggers:
        _table((report.get("triggers", {}) or {}).get("triggers"))

    with tab_symbol:
        _table((report.get("triggers", {}) or {}).get("by_symbol"))

    with tab_positions:
        _table((report.get("triggers", {}) or {}).get("positions"))

    with tab_playbook:
        _table((report.get("playbook", {}) or {}).get("playbook"))

    return report
