"""
Sprint 8 Phase 5 — Institutional Portfolio Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_risk_engine import build_portfolio_risk_report
from modules.options.options_stress_testing_engine import build_portfolio_stress_report
from modules.options.options_greeks_exposure_engine import build_greeks_exposure_report
from modules.options.options_risk_guardrails_engine import evaluate_portfolio_guardrails
from modules.options.options_portfolio_construction_engine import build_portfolio_construction_report
from modules.options.options_position_lifecycle_engine import build_position_lifecycle_report
from modules.options.options_roll_engine import build_rolling_intelligence_report
from modules.options.options_income_engine import build_income_intelligence_report
from modules.options.options_assignment_engine import build_assignment_expiration_report
from modules.options.options_autonomous_portfolio_manager import build_autonomous_portfolio_manager_report
from modules.options.options_portfolio_command_center import (
    build_command_center_report,
    summarize_command_center,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def _safe_metric(value: Any, default: str = "—") -> Any:
    if value is None:
        return default
    return value


def render_portfolio_command_center_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏦 Institutional Portfolio Command Center")
    st.caption("CIO view · Portfolio health · Risk state · lifecycle queue · roll queue · assignment alerts · autonomous actions")

    refresh = st.button(
        "Refresh Command Center",
        key="portfolio_command_center_refresh",
        use_container_width=True,
    )

    cache_key = f"portfolio_command_center_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building institutional portfolio command center…"):
            if positions is None:
                positions = load_portfolio_positions(ticker=ticker, paper=paper)

            if not positions:
                report = {
                    "available": False,
                    "reason": "No options positions available.",
                }
                st.session_state[cache_key] = report
            else:
                risk_report = build_portfolio_risk_report(positions)
                stress_report = build_portfolio_stress_report(positions)
                greeks_report = build_greeks_exposure_report(positions)

                try:
                    guardrails_report = evaluate_portfolio_guardrails(risk_report)
                except Exception as e:
                    guardrails_report = {
                        "passed": False,
                        "breach_count": 1,
                        "breaches": [f"Guardrail evaluation failed: {e}"],
                        "risk_level": "UNKNOWN",
                    }

                construction_report = build_portfolio_construction_report(positions)
                lifecycle_report = build_position_lifecycle_report(positions)
                roll_report = build_rolling_intelligence_report(positions)
                income_report = build_income_intelligence_report(positions)
                assignment_report = build_assignment_expiration_report(positions)

                autonomous_report = build_autonomous_portfolio_manager_report(
                    positions=positions,
                    portfolio_risk_report=risk_report,
                    stress_report=stress_report,
                    construction_report=construction_report,
                )

                report = build_command_center_report(
                    risk_report=risk_report,
                    stress_report=stress_report,
                    greeks_report=greeks_report,
                    guardrails_report=guardrails_report,
                    construction_report=construction_report,
                    lifecycle_report=lifecycle_report,
                    roll_report=roll_report,
                    income_report=income_report,
                    assignment_report=assignment_report,
                    autonomous_report=autonomous_report,
                )

                st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No command center data available."))
        return report

    health = report.get("health", {})
    queue = report.get("action_queue", {})

    risk = report.get("risk_report", {}) or {}
    construction = report.get("construction_report", {}) or {}
    lifecycle = report.get("lifecycle_report", {}) or {}
    roll = report.get("roll_report", {}) or {}
    income = report.get("income_report", {}) or {}
    assignment = report.get("assignment_report", {}) or {}
    autonomous = report.get("autonomous_report", {}) or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Portfolio Health", health.get("portfolio_health_level", "—"))
    c2.metric("Health Score", f"{health.get('portfolio_health_score', 0)}/100")
    c3.metric("Queued Actions", queue.get("action_count", 0))
    c4.metric("Critical / High", f"{queue.get('critical_count', 0)} / {queue.get('high_count', 0)}")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Risk Score", _safe_metric(_safe_metric(risk.get("risk_score", {})).get("risk_score") if isinstance(risk.get("risk_score"), dict) else risk.get("risk_score", 0)))
    r2.metric("Construction", _safe_metric((construction.get("score", {}) or {}).get("construction_score", 0) if isinstance(construction.get("score"), dict) else 0))
    r3.metric("Lifecycle Actions", _safe_metric((lifecycle.get("summary", {}) or {}).get("action_required_count", 0)))
    r4.metric("Roll Candidates", _safe_metric((roll.get("summary", {}) or {}).get("roll_candidate_count", 0)))

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Assignment Alerts", _safe_metric((assignment.get("summary", {}) or {}).get("assignment_alert_count", 0)))
    a2.metric("Annual Yield", f"{(income.get('summary', {}) or {}).get('annualized_yield', 0):.2f}%")
    a3.metric("Auto State", (autonomous.get("management_state", {}) or {}).get("manager_state", "—"))
    a4.metric("Governance", (autonomous.get("governance", {}) or {}).get("governance_status", "—"))

    st.markdown("#### Command Summary")
    st.info(summarize_command_center(report))

    drivers = health.get("drivers", [])
    if drivers:
        st.markdown("#### Health Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_queue, tab_risk, tab_ops, tab_income, tab_auto, tab_raw = st.tabs(
        [
            "Master Action Queue",
            "Risk State",
            "Operations",
            "Income / Assignment",
            "Autonomous",
            "Raw Reports",
        ]
    )

    with tab_queue:
        _table(queue.get("action_queue"))

    with tab_risk:
        st.markdown("##### Guardrails")
        st.json(report.get("guardrails_report", {}))

        st.markdown("##### Risk")
        st.json({
            "risk_score": risk.get("risk_score"),
            "net_greeks": risk.get("net_greeks"),
        })

        st.markdown("##### Greeks")
        st.json((report.get("greeks_report", {}) or {}).get("summary", {}))

    with tab_ops:
        st.markdown("##### Lifecycle Queue")
        _table((lifecycle.get("action_queue", {}) or {}).get("action_queue"))

        st.markdown("##### Roll Queue")
        _table(roll.get("roll_queue"))

    with tab_income:
        st.markdown("##### Income Summary")
        st.json(income.get("summary", {}))

        st.markdown("##### Assignment Alerts")
        _table(assignment.get("alert_queue"))

    with tab_auto:
        st.markdown("##### Autonomous Manager")
        st.json(autonomous.get("management_state", {}))

        st.markdown("##### Autonomous Queue")
        _table((autonomous.get("action_queue", {}) or {}).get("action_queue"))

    with tab_raw:
        st.json({
            "health": health,
            "action_queue": {
                "action_count": queue.get("action_count"),
                "critical_count": queue.get("critical_count"),
                "high_count": queue.get("high_count"),
            },
        })

    return report
