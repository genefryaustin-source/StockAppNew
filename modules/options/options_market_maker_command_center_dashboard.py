"""
Sprint 11 Phase 5 — Market Maker Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_dealer_positioning_engine import build_dealer_positioning_report
from modules.options.options_gamma_exposure_engine import build_gamma_exposure_report
from modules.options.options_dealer_hedging_flow_engine import build_dealer_hedging_flow_report
from modules.options.options_liquidity_provider_engine import build_liquidity_provider_report
from modules.options.options_market_maker_command_center import (
    DEFAULT_MM_COMMAND_POLICY,
    build_market_maker_command_center_report,
    summarize_market_maker_command_center,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_market_maker_command_center_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    st.subheader("🏦 Market Maker Command Center")
    st.caption("Dealer positioning · gamma exposure · hedge-flow pressure · liquidity provider intelligence")

    with st.expander("Market Maker Command Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        high_threshold = c1.number_input(
            "High Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_MM_COMMAND_POLICY["high_score_threshold"]),
            step=5,
            key="mm_cmd_high_threshold",
        )

        elevated_threshold = c2.number_input(
            "Elevated Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_MM_COMMAND_POLICY["elevated_score_threshold"]),
            step=5,
            key="mm_cmd_elevated_threshold",
        )

        normal_threshold = c3.number_input(
            "Normal Score Threshold",
            min_value=0,
            max_value=100,
            value=int(DEFAULT_MM_COMMAND_POLICY["normal_score_threshold"]),
            step=5,
            key="mm_cmd_normal_threshold",
        )

    policy = dict(DEFAULT_MM_COMMAND_POLICY)
    policy.update({
        "high_score_threshold": float(high_threshold),
        "elevated_score_threshold": float(elevated_threshold),
        "normal_score_threshold": float(normal_threshold),
    })

    refresh = st.button(
        "Refresh Market Maker Command Center",
        key="market_maker_command_refresh",
        use_container_width=True,
    )

    cache_key = f"market_maker_command_center_{ticker}_{paper}"

    if refresh and cache_key in st.session_state:
        del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Building market maker command center…"):
            if chain_data is None:
                chain_key = f"opt_chain_{ticker}"
                payload = st.session_state.get(chain_key)
                chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

            if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
                chain_data = get_options_chain(ticker)
                st.session_state[f"opt_chain_{ticker}"] = chain_data

            dealer_report = build_dealer_positioning_report(
                chain_data=chain_data,
                underlying_price=underlying_price,
            )

            gamma_report = build_gamma_exposure_report(
                chain_data=chain_data,
                underlying_price=underlying_price,
            )

            hedging_report = build_dealer_hedging_flow_report(
                chain_data=chain_data,
                underlying_price=underlying_price,
            )

            liquidity_report = build_liquidity_provider_report(
                chain_data=chain_data,
            )

            report = build_market_maker_command_center_report(
                dealer_report=dealer_report,
                gamma_report=gamma_report,
                hedging_report=hedging_report,
                liquidity_report=liquidity_report,
                policy=policy,
            )

            st.session_state[cache_key] = report

    report = st.session_state[cache_key]

    if not report.get("available"):
        st.info(report.get("reason", "No market maker command data available."))
        return report

    score = report.get("score", {})
    regime = report.get("regime", {})
    opps = report.get("opportunities", {})
    playbook = report.get("playbook", {})

    dealer_summary = (report.get("dealer_report", {}) or {}).get("summary", {})
    gamma_summary = (report.get("gamma_report", {}) or {}).get("summary", {})
    hedging_summary = (report.get("hedging_report", {}) or {}).get("summary", {})
    liquidity_summary = (report.get("liquidity_report", {}) or {}).get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MM Rating", score.get("rating", "—"))
    c2.metric("MM Score", f"{score.get('score', 0)}/100")
    c3.metric("MM Regime", regime.get("market_maker_regime", "—"))
    c4.metric("High Priority", opps.get("high_priority_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Dealer Gamma", dealer_summary.get("gamma_regime", "—"))
    d2.metric("Gamma Exposure", gamma_summary.get("gamma_regime", "—"))
    d3.metric("Hedge Flow", hedging_summary.get("hedging_flow_regime", "—"))
    d4.metric("Liquidity", liquidity_summary.get("liquidity_regime", "—"))

    e1, e2, e3, e4 = st.columns(4)
    e1.metric("Gamma Flip", gamma_summary.get("gamma_flip", dealer_summary.get("gamma_flip", 0)))
    e2.metric("Call Wall", dealer_summary.get("top_call_wall", 0))
    e3.metric("Put Wall", dealer_summary.get("top_put_wall", 0))
    e4.metric("SR Levels", (report.get("support_resistance", {}) or {}).get("level_count", 0))

    st.markdown("#### Market Maker Summary")
    st.info(summarize_market_maker_command_center(report))

    drivers = regime.get("drivers", [])
    if drivers:
        st.markdown("#### Regime Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_exec, tab_dealer, tab_gamma, tab_flow, tab_liquidity, tab_sr, tab_queue, tab_playbook = st.tabs(
        [
            "Executive",
            "Dealer Positioning",
            "Gamma Exposure",
            "Hedging Flow",
            "Liquidity Providers",
            "Support / Resistance",
            "Opportunity Queue",
            "Playbook",
        ]
    )

    with tab_exec:
        component_rows = []
        for key, label in [
            ("dealer_component", "Dealer Positioning"),
            ("gamma_component", "Gamma Exposure"),
            ("hedging_component", "Hedging Flow"),
            ("liquidity_component", "Liquidity Providers"),
        ]:
            comp = score.get(key, {})
            component_rows.append({
                "Component": label,
                "Score": comp.get("score", 0),
                "Label": comp.get("label", "—"),
                "Drivers": "; ".join(comp.get("drivers", [])),
            })
        _table(pd.DataFrame(component_rows))

    with tab_dealer:
        st.json(dealer_summary)
        _table((report.get("dealer_report", {}) or {}).get("recommendations"))

    with tab_gamma:
        st.json(gamma_summary)
        _table((report.get("gamma_report", {}) or {}).get("strike_gex"))

    with tab_flow:
        st.json(hedging_summary)
        _table(((report.get("hedging_report", {}) or {}).get("zones", {}) or {}).get("pressure_zones"))

    with tab_liquidity:
        st.json(liquidity_summary)
        _table((report.get("liquidity_report", {}) or {}).get("recommendations"))

    with tab_sr:
        _table((report.get("support_resistance", {}) or {}).get("support_resistance_map"))

    with tab_queue:
        _table((report.get("opportunities", {}) or {}).get("opportunity_queue"))

    with tab_playbook:
        _table(playbook.get("playbook"))

    return report
