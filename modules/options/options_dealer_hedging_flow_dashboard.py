"""
Sprint 11 Phase 3 — Dealer Hedging Flow Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_dealer_hedging_flow_engine import (
    DEFAULT_DEALER_HEDGING_FLOW_POLICY,
    build_dealer_hedging_flow_report,
    summarize_dealer_hedging_flow,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_dealer_hedging_flow_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    st.subheader("🌊 Dealer Hedging Flow Engine")
    st.caption("Dealer hedge-flow proxy · gamma re-hedging pressure · buy/sell pressure zones")

    with st.expander("Dealer Hedging Flow Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        shock_pct = c1.number_input(
            "Spot Move Shock %",
            min_value=0.1,
            max_value=10.0,
            value=float(DEFAULT_DEALER_HEDGING_FLOW_POLICY["spot_move_shock_pct"]),
            step=0.1,
            key="dealer_flow_spot_move_shock_pct",
        )

        high_flow = c2.number_input(
            "High Flow Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_HEDGING_FLOW_POLICY["high_flow_threshold"]),
            step=100000,
            key="dealer_flow_high_threshold",
        )

        medium_flow = c3.number_input(
            "Medium Flow Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_HEDGING_FLOW_POLICY["medium_flow_threshold"]),
            step=50000,
            key="dealer_flow_medium_threshold",
        )

        d1, d2 = st.columns(2)

        gamma_accel = d1.number_input(
            "Gamma Acceleration Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_HEDGING_FLOW_POLICY["gamma_acceleration_threshold"]),
            step=50000,
            key="dealer_flow_gamma_accel_threshold",
        )

        contract_multiplier = d2.number_input(
            "Contract Multiplier",
            min_value=1,
            value=int(DEFAULT_DEALER_HEDGING_FLOW_POLICY["contract_multiplier"]),
            step=1,
            key="dealer_flow_contract_multiplier",
        )

    policy = dict(DEFAULT_DEALER_HEDGING_FLOW_POLICY)
    policy.update({
        "spot_move_shock_pct": float(shock_pct),
        "high_flow_threshold": float(high_flow),
        "medium_flow_threshold": float(medium_flow),
        "gamma_acceleration_threshold": float(gamma_accel),
        "contract_multiplier": float(contract_multiplier),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_dealer_hedging_flow_report(
        chain_data=chain_data,
        underlying_price=underlying_price,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No dealer hedging-flow data available."))
        return report

    summary = report.get("summary", {})
    regime = report.get("regime", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Flow Regime", summary.get("hedging_flow_regime", "—"))
    c2.metric("Intensity", summary.get("flow_intensity", "—"))
    c3.metric("Up Bias", summary.get("up_move_bias", "—"))
    c4.metric("Down Bias", summary.get("down_move_bias", "—"))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Flow Up", f"{summary.get('total_hedge_flow_up', 0):,.0f}")
    d2.metric("Flow Down", f"{summary.get('total_hedge_flow_down', 0):,.0f}")
    d3.metric("Abs Pressure", f"{summary.get('total_absolute_flow_pressure', 0):,.0f}")
    d4.metric("Top Pressure Strike", summary.get("top_pressure_strike", 0))

    e1, e2, e3 = st.columns(3)
    e1.metric("Delta Notional", f"{summary.get('total_dealer_delta_notional', 0):,.0f}")
    e2.metric("Gamma Rehedge Up", f"{summary.get('total_gamma_rehedge_up', 0):,.0f}")
    e3.metric("Gamma Acceleration", summary.get("gamma_acceleration", "—"))

    st.markdown("#### Dealer Hedging Flow Summary")
    st.info(summarize_dealer_hedging_flow(report))

    drivers = regime.get("drivers", [])
    if drivers:
        st.markdown("#### Hedging Flow Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_recs, tab_zones, tab_strike, tab_expiry, tab_chain = st.tabs(
        [
            "Recommendations",
            "Pressure Zones",
            "By Strike",
            "By Expiry",
            "Chain Diagnostics",
        ]
    )

    with tab_recs:
        _table(report.get("recommendations"))

    with tab_zones:
        _table(
            (report.get("zones", {}) or {}).get("pressure_zones"),
            [
                "strike",
                "absolute_flow_pressure",
                "pressure_rank",
                "net_hedge_flow_up",
                "net_hedge_flow_down",
                "gamma_rehedge_notional_up",
                "gamma_rehedge_notional_down",
                "dealer_delta_notional",
                "open_interest",
                "volume",
            ],
        )

    with tab_strike:
        _table(
            (report.get("flow", {}) or {}).get("by_strike"),
            [
                "strike",
                "dealer_delta_notional",
                "gamma_rehedge_notional_up",
                "gamma_rehedge_notional_down",
                "net_hedge_flow_up",
                "net_hedge_flow_down",
                "absolute_flow_pressure",
                "open_interest",
                "volume",
            ],
        )

    with tab_expiry:
        _table(
            (report.get("flow", {}) or {}).get("by_expiry"),
            [
                "expiry",
                "dte",
                "dealer_delta_notional",
                "gamma_rehedge_notional_up",
                "gamma_rehedge_notional_down",
                "net_hedge_flow_up",
                "net_hedge_flow_down",
                "absolute_flow_pressure",
                "open_interest",
                "volume",
            ],
        )

    with tab_chain:
        _table(
            (report.get("flow", {}) or {}).get("chain"),
            [
                "expiry",
                "dte",
                "type",
                "strike",
                "open_interest",
                "volume",
                "delta",
                "gamma",
                "dealer_delta_notional",
                "gamma_rehedge_notional_up",
                "gamma_rehedge_notional_down",
                "net_hedge_flow_up",
                "net_hedge_flow_down",
                "absolute_flow_pressure",
            ],
        )

    return report
