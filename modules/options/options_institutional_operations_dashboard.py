"""
Sprint 9 Phase 1 — Institutional Portfolio Operations Dashboard.
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
from modules.options.options_portfolio_command_center import build_command_center_report
from modules.options.options_institutional_operations_engine import (
    DEFAULT_OPERATIONS_POLICY,
    build_institutional_operations_report,
    summarize_institutional_operations,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_institutional_operations_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏢 Institutional Portfolio Operations")
    st.caption("Daily operating state · workload queue · playbook · CIO operating workflow")

    with st.expander("Operations Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        max_open_actions = c1.number_input(
            "Max Open Actions",
            min_value=1,
            max_value=250,
            value=int(DEFAULT_OPERATIONS_POLICY["max_open_actions"]),
            step=1,
            key="ops_max_open_actions",
        )

        max_high_actions = c2.number_input(
            "Max High Actions",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_OPERATIONS_POLICY["max_high_actions"]),
            step=1,
            key="ops_max_high_actions",
        )

        target_health = c3.number_input(
            "Target Health Score",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_OPERATIONS_POLICY["target_health_score"]),
            step=5,
            key="ops_target_health",
        )

    policy = dict(DEFAULT_OPERATIONS_POLICY)
    policy.update({
        "max_open_actions": int(max_open_actions),
        "max_high_actions": int(max_high_actions),
        "target_health_score": float(target_health),
    })

    refresh = st.button(
        "Refresh Operations",
        key="institutional_operations_refresh",
        use_container_width=True,
    )

    cache_key = f"institutional_operations_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building institutional operations context…"):
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

                command_report = build_command_center_report(
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

                report = build_institutional_operations_report(
                    command_report=command_report,
                    lifecycle_report=lifecycle_report,
                    roll_report=roll_report,
                    assignment_report=assignment_report,
                    income_report=income_report,
                    autonomous_report=autonomous_report,
                    policy=policy,
                )

                report["command_report"] = command_report
                st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No operations data available."))
        return report

    state = report.get("operating_state", {})
    workload = report.get("workload", {})
    playbook = report.get("playbook", {})
    command = report.get("command_report", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operating State", state.get("operating_state", "—"))
    c2.metric("Pressure Score", f"{state.get('operations_pressure_score', 0)}/100")
    c3.metric("Open Items", workload.get("workload_count", 0))
    c4.metric("Health", f"{state.get('portfolio_health_score', 0)}/100")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Critical", state.get("critical_action_count", 0))
    d2.metric("High Priority", state.get("high_action_count", 0))
    d3.metric("Health Level", state.get("portfolio_health_level", "—"))
    d4.metric("Command Queue", (command.get("action_queue", {}) or {}).get("action_count", 0))

    st.markdown("#### Operations Summary")
    st.info(summarize_institutional_operations(report))

    drivers = state.get("drivers", [])
    if drivers:
        st.markdown("#### Operating Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_workload, tab_playbook, tab_source, tab_priority, tab_command = st.tabs(
        [
            "Workload Queue",
            "Operating Playbook",
            "By Source",
            "By Priority",
            "Command Snapshot",
        ]
    )

    with tab_workload:
        _table(workload.get("workload"))

    with tab_playbook:
        _table(playbook.get("playbook"))

    with tab_source:
        _table(workload.get("by_source"))

    with tab_priority:
        _table(workload.get("by_priority"))

    with tab_command:
        st.json({
            "health": command.get("health", {}),
            "action_queue": {
                "action_count": (command.get("action_queue", {}) or {}).get("action_count"),
                "critical_count": (command.get("action_queue", {}) or {}).get("critical_count"),
                "high_count": (command.get("action_queue", {}) or {}).get("high_count"),
            },
        })

    return report
