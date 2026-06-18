"""
Sprint 6 Phase 2 — Liquidity Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_liquidity_engine import (
    build_liquidity_intelligence_report,
    summarize_liquidity_intelligence,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_liquidity_intelligence_dashboard(
    ticker: str,
    chain_data: dict | None = None,
) -> dict[str, Any]:
    st.subheader("💧 Liquidity Intelligence")
    st.caption("Bid/ask quality · Volume depth · Open interest quality · Tradability score · Institutional capacity")

    chain_key = f"opt_chain_{ticker}"
    if chain_data is None:
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if not chain_data:
        with st.spinner(f"Loading options chain for {ticker}..."):
            chain_data = get_options_chain(ticker)
            st.session_state[chain_key] = chain_data

    report = build_liquidity_intelligence_report(chain_data)

    if not report.get("available"):
        st.info(report.get("reason", "No liquidity data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liquidity Grade", summary.get("market_liquidity_grade", "—"))
    c2.metric("Avg Score", f"{summary.get('avg_liquidity_score', 0)}/100")
    c3.metric("Liquid Contracts", summary.get("liquid_contracts", 0))
    c4.metric("Tradable Contracts", summary.get("tradable_contracts", 0))

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Avg Spread", f"{summary.get('avg_spread_pct', 0)}%")
    s2.metric("Total Volume", f"{summary.get('total_volume', 0):,}")
    s3.metric("Open Interest", f"{summary.get('total_open_interest', 0):,}")
    s4.metric("Dollar Volume", f"${summary.get('total_dollar_volume', 0):,.0f}")

    st.markdown("#### Liquidity Summary")
    st.info(summarize_liquidity_intelligence(report))

    tab_best, tab_expiry, tab_strike, tab_all = st.tabs(
        [
            "Best Contracts",
            "By Expiry",
            "By Strike",
            "All Contracts",
        ]
    )

    with tab_best:
        best = report.get("best_contracts", {}).get("best_contracts")
        _table(best)

    with tab_expiry:
        by_expiry = report.get("by_expiry", {}).get("by_expiry")
        _table(by_expiry)

    with tab_strike:
        by_strike = report.get("by_strike", {}).get("by_strike")
        _table(by_strike)

    with tab_all:
        contracts = report.get("contracts")
        show_cols = [
            "option_symbol",
            "expiry",
            "type",
            "strike",
            "bid",
            "ask",
            "mid",
            "spread",
            "spread_pct",
            "volume",
            "open_interest",
            "liquidity_score",
            "liquidity_grade",
            "execution_difficulty",
            "capacity_contracts",
            "recommended_order_contracts",
        ]
        if isinstance(contracts, pd.DataFrame) and not contracts.empty and "spread_pct" in contracts.columns:
            contracts = contracts.copy()
            contracts["spread_pct"] = (contracts["spread_pct"] * 100).round(2)
        _table(contracts, show_cols)

    return report
