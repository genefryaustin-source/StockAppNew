"""
Sprint 9 Phase 5 — Institutional Income Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_data_service import get_options_chain
from modules.options.options_income_engine import build_income_intelligence_report
from modules.options.options_wheel_engine import build_wheel_command_report
from modules.options.options_covered_call_factory_engine import build_covered_call_candidates
from modules.options.options_cash_secured_put_factory_engine import build_cash_secured_put_report
from modules.options.options_roll_engine import build_rolling_intelligence_report
from modules.options.options_assignment_engine import build_assignment_expiration_report
from modules.options.options_income_command_center import (
    DEFAULT_INCOME_COMMAND_POLICY,
    build_institutional_income_command_report,
    summarize_income_command,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_income_command_center_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("💰 Institutional Income Command Center")
    st.caption("Income health · premium queue · wheel actions · covered call factory · CSP factory · assignment/roll risk")

    with st.expander("Income Command Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        target_yield = c1.number_input(
            "Target Annualized Yield %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_INCOME_COMMAND_POLICY["target_annualized_yield"]),
            step=0.5,
            key="income_command_target_yield",
        )

        max_assignment = c2.number_input(
            "Max Assignment Alerts",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_INCOME_COMMAND_POLICY["max_assignment_alerts"]),
            step=1,
            key="income_command_max_assignment",
        )

        max_roll_queue = c3.number_input(
            "Max Roll Queue",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_INCOME_COMMAND_POLICY["max_roll_queue"]),
            step=1,
            key="income_command_max_roll_queue",
        )

        p1, p2 = st.columns(2)
        portfolio_cash = p1.number_input(
            "Portfolio Cash for CSP Factory ($)",
            min_value=0.0,
            value=100000.0,
            step=1000.0,
            key="income_command_portfolio_cash",
        )

        min_health = p2.number_input(
            "Minimum Income Health Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_INCOME_COMMAND_POLICY["min_income_health_score"]),
            step=5,
            key="income_command_min_health",
        )

    policy = dict(DEFAULT_INCOME_COMMAND_POLICY)
    policy.update({
        "target_annualized_yield": float(target_yield),
        "max_assignment_alerts": int(max_assignment),
        "max_roll_queue": int(max_roll_queue),
        "min_income_health_score": float(min_health),
    })

    refresh = st.button(
        "Refresh Income Command Center",
        key="income_command_center_refresh",
        use_container_width=True,
    )

    cache_key = f"income_command_center_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building income command center…"):
            if positions is None:
                positions = load_portfolio_positions(ticker=ticker, paper=paper)

            if chain_data is None:
                chain_key = f"opt_chain_{ticker}"
                payload = st.session_state.get(chain_key)
                chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

            if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
                try:
                    chain_data = get_options_chain(ticker)
                    st.session_state[f"opt_chain_{ticker}"] = chain_data
                except Exception:
                    chain_data = None

            income_report = build_income_intelligence_report(positions)
            wheel_report = build_wheel_command_report(positions)
            covered_call_report = build_covered_call_candidates(positions=positions, chain_data=chain_data)
            csp_report = build_cash_secured_put_report(
                chain_data=chain_data,
                portfolio_cash=float(portfolio_cash),
            ) if chain_data is not None else {
                "available": False,
                "reason": "No chain data available for CSP Factory.",
                "summary": {},
                "approved": pd.DataFrame(),
                "candidates": pd.DataFrame(),
            }
            roll_report = build_rolling_intelligence_report(positions)
            assignment_report = build_assignment_expiration_report(positions)

            report = build_institutional_income_command_report(
                income_report=income_report,
                wheel_report=wheel_report,
                covered_call_report=covered_call_report,
                csp_report=csp_report,
                roll_report=roll_report,
                assignment_report=assignment_report,
                policy=policy,
            )

            st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No income command center data available."))
        return report

    health = report.get("health", {})
    queue = report.get("queue", {})
    income = report.get("income_report", {}) or {}
    wheel = report.get("wheel_report", {}) or {}
    csp = report.get("csp_report", {}) or {}
    cc = report.get("covered_call_report", {}) or {}
    assignment = report.get("assignment_report", {}) or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Income Health", health.get("income_health_level", "—"))
    c2.metric("Health Score", f"{health.get('income_health_score', 0)}/100")
    c3.metric("Annualized Yield", f"{health.get('annualized_yield', 0)}%")
    c4.metric("Income Actions", queue.get("action_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Wheel Actions", (wheel.get("summary", {}) or {}).get("wheel_action_count", 0))
    d2.metric("CC Candidates", cc.get("candidate_count", 0))
    d3.metric("CSP Approved", (csp.get("summary", {}) or {}).get("approved_count", 0))
    d4.metric("Assignment Alerts", (assignment.get("summary", {}) or {}).get("assignment_alert_count", 0))

    st.markdown("#### Income Command Summary")
    st.info(summarize_income_command(report))

    drivers = health.get("drivers", [])
    if drivers:
        st.markdown("#### Income Health Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_queue, tab_sources, tab_wheel, tab_cc, tab_csp, tab_assignment = st.tabs(
        [
            "Income Action Queue",
            "Income Sources",
            "Wheel",
            "Covered Calls",
            "Cash Secured Puts",
            "Assignment / Expiration",
        ]
    )

    with tab_queue:
        _table(queue.get("income_action_queue"))

    with tab_sources:
        _table((report.get("sources", {}) or {}).get("income_sources"))

    with tab_wheel:
        _table(wheel.get("action_queue"))

    with tab_cc:
        _table(cc.get("candidates"))

    with tab_csp:
        _table(csp.get("approved"))

    with tab_assignment:
        _table(assignment.get("alert_queue"))

    return report
