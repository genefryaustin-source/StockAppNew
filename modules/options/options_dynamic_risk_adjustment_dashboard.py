"""
Sprint 7 Phase 2 — Dynamic Risk Adjustment Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_risk_engine import build_portfolio_risk_report
from modules.options.options_stress_testing_engine import build_portfolio_stress_report
from modules.options.options_greeks_exposure_engine import build_greeks_exposure_report
from modules.options.options_portfolio_hedging_engine import build_portfolio_hedging_report
from modules.options.options_dynamic_risk_adjustment_engine import (
    DEFAULT_RISK_ADJUSTMENT_POLICY,
    build_dynamic_risk_adjustment_report,
    summarize_dynamic_risk_adjustment,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_dynamic_risk_adjustment_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🧭 Dynamic Risk Adjustment")
    st.caption("Risk-state detection · Exposure scaling · Defensive rebalance · Adjustment actions")

    with st.expander("Risk Adjustment Policy", expanded=False):
        c1, c2, c3 = st.columns(3)
        max_portfolio_risk = c1.number_input(
            "Max Portfolio Risk Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_RISK_ADJUSTMENT_POLICY["max_portfolio_risk_score"]),
            step=5,
            key="dra_max_portfolio_risk",
        )
        max_greeks_risk = c2.number_input(
            "Max Greeks Risk Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_RISK_ADJUSTMENT_POLICY["max_greeks_risk_score"]),
            step=5,
            key="dra_max_greeks_risk",
        )
        max_stress_loss = c3.number_input(
            "Max Stress Loss %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_RISK_ADJUSTMENT_POLICY["max_stress_loss_pct"]),
            step=1.0,
            key="dra_max_stress_loss",
        )

        d1, d2, d3 = st.columns(3)
        min_liquidity = d1.number_input(
            "Min Liquidity Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_RISK_ADJUSTMENT_POLICY["min_liquidity_score"]),
            step=5,
            key="dra_min_liquidity",
        )
        max_hedge_need = d2.number_input(
            "Max Hedge Need Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_RISK_ADJUSTMENT_POLICY["max_hedge_need_score"]),
            step=5,
            key="dra_max_hedge_need",
        )
        risk_off_scale = d3.number_input(
            "Risk-Off Scale",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_RISK_ADJUSTMENT_POLICY["risk_off_scale"]),
            step=0.05,
            key="dra_risk_off_scale",
        )

        regime = st.selectbox(
            "Market / Volatility Regime",
            ["Neutral", "Risk-On", "Defensive", "High Vol", "Risk-Off", "Crash"],
            index=0,
            key="dra_market_regime",
        )

    policy = dict(DEFAULT_RISK_ADJUSTMENT_POLICY)
    policy.update({
        "max_portfolio_risk_score": float(max_portfolio_risk),
        "max_greeks_risk_score": float(max_greeks_risk),
        "max_stress_loss_pct": float(max_stress_loss),
        "min_liquidity_score": float(min_liquidity),
        "max_hedge_need_score": float(max_hedge_need),
        "risk_off_scale": float(risk_off_scale),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    if not positions:
        st.info("No options positions available.")
        return {"available": False, "reason": "No options positions available."}

    with st.spinner("Building risk context…"):
        portfolio_risk = build_portfolio_risk_report(positions)
        stress = build_portfolio_stress_report(positions)
        greeks = build_greeks_exposure_report(positions)
        hedge = build_portfolio_hedging_report(positions)

    report = build_dynamic_risk_adjustment_report(
        positions=positions,
        portfolio_risk_report=portfolio_risk,
        stress_report=stress,
        greeks_report=greeks,
        hedge_report=hedge,
        market_regime=regime,
        volatility_regime=regime,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No dynamic risk data available."))
        return report

    risk_state = report.get("risk_state", {})
    scale = report.get("exposure_scale", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk State", risk_state.get("risk_state", "—"))
    c2.metric("Pressure Score", f"{risk_state.get('risk_pressure_score', 0)}/100")
    c3.metric("Action", scale.get("recommended_action", "—"))
    c4.metric("Target Exposure", f"{scale.get('target_exposure_pct', 0)}%")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Portfolio Risk", risk_state.get("portfolio_risk_score", 0))
    d2.metric("Greeks Risk", risk_state.get("greeks_risk_score", 0))
    d3.metric("Stress Loss", f"{risk_state.get('worst_stress_loss_pct', 0)}%")
    d4.metric("Hedge Need", risk_state.get("hedge_need_score", 0))

    st.markdown("#### Dynamic Risk Summary")
    st.info(summarize_dynamic_risk_adjustment(report))

    drivers = risk_state.get("drivers", [])
    if drivers:
        st.markdown("#### Risk Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_actions, tab_plan, tab_state, tab_positions = st.tabs(
        [
            "Actions",
            "Adjustment Plan",
            "Risk State",
            "Positions",
        ]
    )

    with tab_actions:
        _table(report.get("actions", {}).get("actions"))

    with tab_plan:
        _table(report.get("adjustment_plan", {}).get("adjustment_plan"))

    with tab_state:
        st.json(risk_state)
        st.json(scale)

    with tab_positions:
        positions_df = report.get("positions")
        show_cols = [
            "underlying",
            "option_symbol",
            "option_type",
            "expiry",
            "strike",
            "qty",
            "market_value",
            "notional_proxy",
            "net_delta",
            "net_gamma",
            "net_theta",
            "net_vega",
        ]
        _table(positions_df, show_cols)

    return report
