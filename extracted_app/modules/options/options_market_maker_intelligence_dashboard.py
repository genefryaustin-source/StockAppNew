"""
Sprint 4 Phase 3 — Market Maker Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_market_maker_pressure_engine import (
    build_market_maker_pressure_report,
    summarize_market_maker_pressure,
)


def _get_underlying_price(chain_data: dict[str, Any] | None) -> float | None:
    if not chain_data:
        return None
    for key in ("underlying_price", "price", "spot", "last_price"):
        try:
            val = chain_data.get(key)
            if val is not None:
                return float(val)
        except Exception:
            pass
    return None


def render_market_maker_intelligence_dashboard(
    ticker: str,
    chain_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader(f"🏦 Market Maker Intelligence — {ticker.upper()}")
    st.caption("Dealer positioning · Gamma flip · Hedging flow · Market-maker pressure")

    if chain_data is None:
        with st.spinner(f"Loading options chain for {ticker.upper()}…"):
            chain_data = get_options_chain(ticker)

    if not chain_data or chain_data.get("error"):
        st.error((chain_data or {}).get("error", f"No chain data available for {ticker.upper()}"))
        return {}

    expirations = chain_data.get("expirations", [])
    if not expirations:
        st.warning("No expirations available.")
        return {}

    expiry = st.selectbox(
        "Expiration",
        expirations,
        index=0,
        key=f"mm_intel_expiry_{ticker.upper()}",
    )

    underlying_price = _get_underlying_price(chain_data)

    report = build_market_maker_pressure_report(
        chain_data=chain_data,
        expiry=expiry,
        underlying_price=underlying_price,
    )

    if not report.get("available"):
        st.warning(report.get("reason", "Market maker intelligence unavailable."))
        return report

    dealer = report["dealer"]
    gamma = report["gamma_flip"]
    hedging = report["hedging"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MM Pressure", report.get("pressure_regime", "—"))
    c2.metric("Pressure Score", f"{report.get('pressure_score', 0)}/100")
    c3.metric("Gamma Regime", dealer.get("gamma_regime", "—"))
    c4.metric("Hedging Risk", hedging.get("risk_level", "—"))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Gamma Flip", "—" if gamma.get("gamma_flip") is None else f"${float(gamma.get('gamma_flip')):,.2f}")
    g2.metric("Net Dealer Delta", f"{dealer.get('net_dealer_delta', 0):,.0f}")
    g3.metric("Net Dealer Gamma", f"{dealer.get('net_dealer_gamma', 0):,.0f}")
    g4.metric("Move Behavior", hedging.get("move_behavior", "—"))

    st.markdown("#### Institutional Summary")
    st.markdown(f"- {summarize_market_maker_pressure(report)}")
    for line in report.get("summary", []):
        st.markdown(f"- {line}")

    with st.expander("Dealer Exposure by Strike", expanded=False):
        table = dealer.get("by_strike")
        if isinstance(table, pd.DataFrame) and not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption("No dealer exposure table available.")

    with st.expander("Gamma Flip Table", expanded=False):
        table = gamma.get("gamma_table")
        if isinstance(table, pd.DataFrame) and not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption("No gamma flip table available.")

    return report
