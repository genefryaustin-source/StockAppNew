"""
Sprint 10 Phase 1 — Volatility Surface Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_volatility_surface_engine import (
    DEFAULT_SURFACE_POLICY,
    build_volatility_surface_report,
    summarize_volatility_surface,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_volatility_surface_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
    underlying_price: float | None = None,
) -> dict[str, Any]:
    st.subheader("🌋 Volatility Surface Intelligence")
    st.caption("IV surface · skew · term structure · moneyness zones · surface opportunities")

    with st.expander("Surface Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        atm_band = c1.number_input(
            "ATM Band %",
            min_value=1.0,
            max_value=25.0,
            value=float(DEFAULT_SURFACE_POLICY["atm_moneyness_band_pct"]),
            step=0.5,
            key="surface_atm_band",
        )

        wing_band = c2.number_input(
            "Wing Band %",
            min_value=5.0,
            max_value=50.0,
            value=float(DEFAULT_SURFACE_POLICY["wing_moneyness_band_pct"]),
            step=1.0,
            key="surface_wing_band",
        )

        steep_skew = c3.number_input(
            "Steep Skew Threshold",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_SURFACE_POLICY["steep_skew_threshold"]),
            step=0.01,
            key="surface_steep_skew",
        )

        d1, d2, d3 = st.columns(3)

        high_iv = d1.number_input(
            "High IV Threshold",
            min_value=0.01,
            max_value=3.0,
            value=float(DEFAULT_SURFACE_POLICY["high_iv_threshold"]),
            step=0.01,
            key="surface_high_iv",
        )

        low_iv = d2.number_input(
            "Low IV Threshold",
            min_value=0.01,
            max_value=3.0,
            value=float(DEFAULT_SURFACE_POLICY["low_iv_threshold"]),
            step=0.01,
            key="surface_low_iv",
        )

        term_inv = d3.number_input(
            "Term Inversion Threshold",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_SURFACE_POLICY["term_inversion_threshold"]),
            step=0.01,
            key="surface_term_inversion",
        )

    policy = dict(DEFAULT_SURFACE_POLICY)
    policy.update({
        "atm_moneyness_band_pct": float(atm_band),
        "wing_moneyness_band_pct": float(wing_band),
        "steep_skew_threshold": float(steep_skew),
        "high_iv_threshold": float(high_iv),
        "low_iv_threshold": float(low_iv),
        "term_inversion_threshold": float(term_inv),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_volatility_surface_report(
        chain_data=chain_data,
        underlying_price=underlying_price,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No volatility surface data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contracts", summary.get("contract_count", 0))
    c2.metric("Expirations", summary.get("expiry_count", 0))
    c3.metric("Avg IV", f"{summary.get('avg_iv', 0):.4f}")
    c4.metric("IV Regime", summary.get("iv_regime", "—"))

    d1, d2, d3 = st.columns(3)
    d1.metric("Term Regime", summary.get("term_regime", "—"))
    d2.metric("Term Slope", f"{summary.get('term_slope', 0):.4f}")
    d3.metric("Opportunities", summary.get("opportunity_count", 0))

    st.markdown("#### Volatility Surface Summary")
    st.info(summarize_volatility_surface(report))

    tab_surface, tab_expiry, tab_skew, tab_term, tab_opps = st.tabs(
        ["Surface Grid", "Expiry Summary", "Skew", "Term Structure", "Opportunities"]
    )

    with tab_surface:
        _table(
            report.get("surface_grid"),
            [
                "expiry", "dte", "strike", "moneyness_pct", "type", "iv",
                "mid", "volume", "open_interest", "delta", "gamma", "theta", "vega",
            ],
        )

    with tab_expiry:
        _table(report.get("expiry_summary"))

    with tab_skew:
        _table((report.get("skew", {}) or {}).get("skew"))

    with tab_term:
        _table((report.get("term", {}) or {}).get("term_structure"))

    with tab_opps:
        _table((report.get("opportunities", {}) or {}).get("opportunities"))

    return report
