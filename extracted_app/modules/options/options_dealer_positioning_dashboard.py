"""
Sprint 11 Phase 1 — Dealer Positioning Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_dealer_positioning_engine import (
    DEFAULT_DEALER_POSITIONING_POLICY,
    build_dealer_positioning_report,
    summarize_dealer_positioning,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_dealer_positioning_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    st.subheader("🏛 Dealer Positioning Intelligence")
    st.caption("Dealer gamma · delta hedge pressure · vega exposure · call/put walls · gamma flip")

    with st.expander("Dealer Positioning Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        gamma_threshold = c1.number_input(
            "Gamma Pressure Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_POSITIONING_POLICY["gamma_pressure_threshold"]),
            step=100000,
            key="dealer_gamma_pressure_threshold",
        )

        delta_threshold = c2.number_input(
            "Delta Pressure Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_POSITIONING_POLICY["delta_pressure_threshold"]),
            step=100000,
            key="dealer_delta_pressure_threshold",
        )

        vega_threshold = c3.number_input(
            "Vega Pressure Threshold",
            min_value=0,
            value=int(DEFAULT_DEALER_POSITIONING_POLICY["vega_pressure_threshold"]),
            step=50000,
            key="dealer_vega_pressure_threshold",
        )

        d1, d2 = st.columns(2)

        wall_quantile = d1.number_input(
            "Wall OI Quantile",
            min_value=0.50,
            max_value=0.99,
            value=float(DEFAULT_DEALER_POSITIONING_POLICY["wall_oi_quantile"]),
            step=0.01,
            key="dealer_wall_oi_quantile",
        )

        near_money_band = d2.number_input(
            "Near Money Band %",
            min_value=1.0,
            max_value=25.0,
            value=float(DEFAULT_DEALER_POSITIONING_POLICY["near_money_band_pct"]),
            step=0.5,
            key="dealer_near_money_band_pct",
        )

    policy = dict(DEFAULT_DEALER_POSITIONING_POLICY)
    policy.update({
        "gamma_pressure_threshold": float(gamma_threshold),
        "delta_pressure_threshold": float(delta_threshold),
        "vega_pressure_threshold": float(vega_threshold),
        "wall_oi_quantile": float(wall_quantile),
        "near_money_band_pct": float(near_money_band),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_dealer_positioning_report(
        chain_data=chain_data,
        underlying_price=underlying_price,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No dealer positioning data available."))
        return report

    summary = report.get("summary", {})
    regime = report.get("regime", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Positioning", summary.get("positioning_regime", "—"))
    c2.metric("Gamma Regime", summary.get("gamma_regime", "—"))
    c3.metric("Delta Regime", summary.get("delta_regime", "—"))
    c4.metric("Vega Regime", summary.get("vega_regime", "—"))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Dealer Gamma", f"{summary.get('total_dealer_gamma', 0):,.0f}")
    d2.metric("Dealer Delta", f"{summary.get('total_dealer_delta', 0):,.0f}")
    d3.metric("Gamma Flip", summary.get("gamma_flip", 0))
    d4.metric("Flip Distance", f"{summary.get('distance_to_flip_pct', 0)}%")

    e1, e2, e3 = st.columns(3)
    e1.metric("Top Call Wall", summary.get("top_call_wall", 0))
    e2.metric("Top Put Wall", summary.get("top_put_wall", 0))
    e3.metric("Recommendations", summary.get("recommendation_count", 0))

    st.markdown("#### Dealer Positioning Summary")
    st.info(summarize_dealer_positioning(report))

    drivers = regime.get("drivers", [])
    if drivers:
        st.markdown("#### Dealer Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_recs, tab_strike, tab_expiry, tab_walls, tab_flip, tab_chain = st.tabs(
        [
            "Recommendations",
            "By Strike",
            "By Expiry",
            "Walls",
            "Gamma Flip",
            "Chain Diagnostics",
        ]
    )

    with tab_recs:
        _table(report.get("recommendations"))

    with tab_strike:
        _table(
            (report.get("exposures", {}) or {}).get("by_strike"),
            [
                "strike",
                "dealer_gamma_exposure",
                "dealer_delta_exposure",
                "dealer_vega_exposure",
                "open_interest",
                "volume",
                "avg_iv",
            ],
        )

    with tab_expiry:
        _table(
            (report.get("exposures", {}) or {}).get("by_expiry"),
            [
                "expiry",
                "dte",
                "dealer_gamma_exposure",
                "dealer_delta_exposure",
                "dealer_vega_exposure",
                "open_interest",
                "volume",
                "avg_iv",
            ],
        )

    with tab_walls:
        st.markdown("##### Call Walls")
        _table((report.get("walls", {}) or {}).get("call_walls"))
        st.markdown("##### Put Walls")
        _table((report.get("walls", {}) or {}).get("put_walls"))

    with tab_flip:
        _table((report.get("gamma_flip", {}) or {}).get("cumulative_gamma_curve"))

    with tab_chain:
        _table(
            (report.get("exposures", {}) or {}).get("chain"),
            [
                "expiry",
                "dte",
                "type",
                "strike",
                "open_interest",
                "volume",
                "iv",
                "delta",
                "gamma",
                "vega",
                "dealer_gamma_exposure",
                "dealer_delta_exposure",
                "dealer_vega_exposure",
            ],
        )

    return report
