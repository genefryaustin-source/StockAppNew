"""
Sprint 10 Phase 5 — Institutional Volatility Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_volatility_surface_engine import build_volatility_surface_report
from modules.options.options_volatility_regime_engine import build_volatility_regime_report
from modules.options.options_term_structure_engine import build_term_structure_report
from modules.options.options_skew_engine import build_skew_intelligence_report
from modules.options.options_volatility_command_center import (
    DEFAULT_VOL_COMMAND_POLICY,
    build_volatility_command_center_report,
    summarize_volatility_command_center,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def _metric_value(value: Any, digits: int = 4) -> str:
    try:
        if isinstance(value, float):
            return f"{value:.{digits}f}"
        return str(value)
    except Exception:
        return "—"


def render_volatility_command_center_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏦 Institutional Volatility Command Center")
    st.caption("Surface · Regime · Term Structure · Skew · Opportunity Queue · Trade Playbook")

    with st.expander("Volatility Command Policy", expanded=False):
        c1, c2, c3 = st.columns(3)
        high_threshold = c1.number_input(
            "High Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_VOL_COMMAND_POLICY["high_score_threshold"]),
            step=5,
            key="vol_cmd_high_threshold",
        )
        elevated_threshold = c2.number_input(
            "Elevated Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_VOL_COMMAND_POLICY["elevated_score_threshold"]),
            step=5,
            key="vol_cmd_elevated_threshold",
        )
        normal_threshold = c3.number_input(
            "Normal Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_VOL_COMMAND_POLICY["normal_score_threshold"]),
            step=5,
            key="vol_cmd_normal_threshold",
        )

    policy = dict(DEFAULT_VOL_COMMAND_POLICY)
    policy.update({
        "high_score_threshold": float(high_threshold),
        "elevated_score_threshold": float(elevated_threshold),
        "normal_score_threshold": float(normal_threshold),
    })

    refresh = st.button("Refresh Volatility Command Center", key="volatility_command_center_refresh", use_container_width=True)
    cache_key = f"volatility_command_center_{ticker}_{paper}"
    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building institutional volatility command center…"):
            if chain_data is None:
                chain_key = f"opt_chain_{ticker}"
                payload = st.session_state.get(chain_key)
                chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

            if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
                chain_data = get_options_chain(ticker)
                st.session_state[f"opt_chain_{ticker}"] = chain_data

            surface_report = build_volatility_surface_report(chain_data)
            regime_report = build_volatility_regime_report(chain_data)
            term_report = build_term_structure_report(chain_data)
            skew_report = build_skew_intelligence_report(chain_data)

            report = build_volatility_command_center_report(
                surface_report=surface_report,
                regime_report=regime_report,
                term_report=term_report,
                skew_report=skew_report,
                policy=policy,
            )
            st.session_state[cache_key] = report

    report = st.session_state[cache_key]
    if not report.get("available"):
        st.info(report.get("reason", "No volatility command center data available."))
        return report

    score = report.get("score", {})
    opps = report.get("opportunities", {})
    playbook = report.get("playbook", {})
    surface_summary = (report.get("surface_report", {}) or {}).get("summary", {})
    regime_summary = (report.get("regime_report", {}) or {}).get("summary", {})
    term_summary = (report.get("term_report", {}) or {}).get("summary", {})
    skew_summary = (report.get("skew_report", {}) or {}).get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Volatility Rating", score.get("rating", "—"))
    c2.metric("Vol Score", f"{score.get('score', 0)}/100")
    c3.metric("Opportunities", opps.get("opportunity_count", 0))
    c4.metric("High Priority", opps.get("high_priority_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("IV Regime", regime_summary.get("current_regime", "—"))
    d2.metric("IV Rank", regime_summary.get("iv_rank", 0))
    d3.metric("Term Regime", term_summary.get("term_regime", "—"))
    d4.metric("Skew Regime", skew_summary.get("regime", "—"))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Avg IV", _metric_value(surface_summary.get("avg_iv", 0)))
    e2.metric("VRP", regime_summary.get("volatility_risk_premium", "—"))
    e3.metric("Term Slope", _metric_value(term_summary.get("term_slope", 0)))
    e4.metric("Risk Reversal", _metric_value(skew_summary.get("risk_reversal", 0)))

    st.markdown("#### Executive Summary")
    st.info(summarize_volatility_command_center(report))

    drivers = []
    for component_name in ["surface_component", "regime_component", "term_component", "skew_component"]:
        component = score.get(component_name, {})
        for driver in component.get("drivers", []):
            drivers.append(f"{component_name.replace('_component', '').title()}: {driver}")
    if drivers:
        st.markdown("#### Command Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_exec, tab_surface, tab_regime, tab_term, tab_skew, tab_opps, tab_playbook = st.tabs([
        "Executive",
        "Vol Surface",
        "Vol Regime",
        "Term Structure",
        "Skew",
        "Opportunities",
        "Trade Playbook",
    ])

    with tab_exec:
        component_rows = []
        for key, label in [
            ("surface_component", "Surface"),
            ("regime_component", "Regime"),
            ("term_component", "Term Structure"),
            ("skew_component", "Skew"),
        ]:
            comp = score.get(key, {})
            component_rows.append({
                "Component": label,
                "Score": comp.get("score", 0),
                "Label": comp.get("label", "—"),
                "Drivers": "; ".join(comp.get("drivers", [])),
            })
        _table(pd.DataFrame(component_rows))

    with tab_surface:
        st.markdown("##### Surface Summary")
        st.json(surface_summary)
        st.markdown("##### Surface Opportunities")
        _table(((report.get("surface_report", {}) or {}).get("opportunities", {}) or {}).get("opportunities"))

    with tab_regime:
        st.markdown("##### Regime Summary")
        st.json(regime_summary)
        st.markdown("##### Regime Recommendations")
        _table((report.get("regime_report", {}) or {}).get("recommendations"))

    with tab_term:
        st.markdown("##### Term Summary")
        st.json(term_summary)
        st.markdown("##### Term Recommendations")
        _table((report.get("term_report", {}) or {}).get("recommendations"))
        st.markdown("##### Term Opportunities")
        _table(((report.get("term_report", {}) or {}).get("opportunities", {}) or {}).get("opportunities"))

    with tab_skew:
        st.markdown("##### Skew Summary")
        st.json(skew_summary)
        st.markdown("##### Skew Opportunities")
        _table((report.get("skew_report", {}) or {}).get("opportunities"))

    with tab_opps:
        _table(opps.get("opportunities"))

    with tab_playbook:
        _table(playbook.get("playbook"))

    return report
