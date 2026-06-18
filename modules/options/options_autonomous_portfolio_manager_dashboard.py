"""
Sprint 7 Phase 5 — Autonomous Portfolio Manager Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_risk_engine import build_portfolio_risk_report
from modules.options.options_stress_testing_engine import build_portfolio_stress_report
from modules.options.options_portfolio_hedging_engine import build_portfolio_hedging_report
from modules.options.options_dynamic_risk_adjustment_engine import build_dynamic_risk_adjustment_report
from modules.options.options_portfolio_construction_engine import build_portfolio_construction_report
from modules.options.options_autonomous_portfolio_manager import (
    DEFAULT_AUTONOMOUS_POLICY,
    build_autonomous_portfolio_manager_report,
    summarize_autonomous_portfolio_manager,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_autonomous_portfolio_manager_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🤖 Autonomous Portfolio Manager")
    st.caption("Decision-support only · Portfolio state · Autonomous recommendations · Governance queue")

    with st.expander("Autonomous Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        autonomy_level = c1.selectbox(
            "Autonomy Level",
            ["OBSERVE", "ADVISORY", "APPROVAL_REQUIRED", "AUTONOMOUS_SIM"],
            index=1,
            key="apm_autonomy_level",
        )

        max_portfolio_risk = c2.number_input(
            "Max Portfolio Risk Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_AUTONOMOUS_POLICY["max_portfolio_risk_score"]),
            step=5,
            key="apm_max_portfolio_risk",
        )

        max_stress_loss = c3.number_input(
            "Max Stress Loss %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_AUTONOMOUS_POLICY["max_stress_loss_pct"]),
            step=1.0,
            key="apm_max_stress_loss",
        )

        d1, d2, d3 = st.columns(3)

        max_hedge_need = d1.number_input(
            "Max Hedge Need Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_AUTONOMOUS_POLICY["max_hedge_need_score"]),
            step=5,
            key="apm_max_hedge_need",
        )

        min_liquidity = d2.number_input(
            "Min Liquidity Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_AUTONOMOUS_POLICY["min_liquidity_score"]),
            step=5,
            key="apm_min_liquidity",
        )

        require_approval = d3.toggle(
            "Require Human Approval",
            value=True,
            key="apm_require_human_approval",
        )

    policy = dict(DEFAULT_AUTONOMOUS_POLICY)
    policy.update({
        "autonomy_level": autonomy_level,
        "max_portfolio_risk_score": float(max_portfolio_risk),
        "max_stress_loss_pct": float(max_stress_loss),
        "max_hedge_need_score": float(max_hedge_need),
        "min_liquidity_score": float(min_liquidity),
        "require_human_approval": bool(require_approval),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    if not positions:
        st.info("No options positions available.")
        return {"available": False, "reason": "No options positions available."}

    with st.spinner("Building autonomous portfolio context…"):
        portfolio_risk = build_portfolio_risk_report(positions)
        stress = build_portfolio_stress_report(positions)
        hedge = build_portfolio_hedging_report(positions)
        construction = build_portfolio_construction_report(positions)
        dynamic = build_dynamic_risk_adjustment_report(
            positions=positions,
            portfolio_risk_report=portfolio_risk,
            stress_report=stress,
            hedge_report=hedge,
            construction_report=construction,
            policy=None,
        )

    report = build_autonomous_portfolio_manager_report(
        positions=positions,
        portfolio_risk_report=portfolio_risk,
        stress_report=stress,
        hedge_report=hedge,
        dynamic_risk_report=dynamic,
        construction_report=construction,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No autonomous portfolio manager data available."))
        return report

    state = report.get("management_state", {})
    governance = report.get("governance", {})
    queue = report.get("action_queue", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Manager State", state.get("manager_state", "—"))
    c2.metric("Pressure Score", f"{state.get('manager_pressure_score', 0)}/100")
    c3.metric("Governance", governance.get("governance_status", "—"))
    c4.metric("Queued Actions", queue.get("action_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Portfolio Risk", state.get("portfolio_risk_score", 0))
    d2.metric("Stress Loss", f"{state.get('stress_loss_pct', 0)}%")
    d3.metric("Hedge Need", state.get("hedge_need_score", 0))
    d4.metric("Construction", state.get("construction_score", 0))

    st.markdown("#### Autonomous Manager Summary")
    st.info(summarize_autonomous_portfolio_manager(report))

    drivers = state.get("drivers", [])
    if drivers:
        st.markdown("#### Manager Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_queue, tab_recs, tab_state, tab_gov, tab_positions = st.tabs(
        [
            "Action Queue",
            "Recommendations",
            "State",
            "Governance",
            "Positions",
        ]
    )

    with tab_queue:
        _table(queue.get("action_queue"))

    with tab_recs:
        _table(report.get("recommendations", {}).get("recommendations"))

    with tab_state:
        st.json(state)

    with tab_gov:
        st.json(governance)

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
