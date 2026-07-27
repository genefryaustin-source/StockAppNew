"""
Sprint 11 Phase 4 — Liquidity Provider Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_liquidity_provider_engine import (
    DEFAULT_LP_POLICY,
    build_liquidity_provider_report,
    summarize_liquidity_provider,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_liquidity_provider_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏪 Liquidity Provider Intelligence")
    st.caption("Spread quality · depth proxy · liquidity regime · execution guidance · stress detection")

    with st.expander("Liquidity Provider Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        tight_spread = c1.number_input(
            "Tight Spread %",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_LP_POLICY["tight_spread_pct"]),
            step=0.01,
            key="lp_tight_spread_pct",
        )

        wide_spread = c2.number_input(
            "Wide Spread %",
            min_value=0.01,
            max_value=2.0,
            value=float(DEFAULT_LP_POLICY["wide_spread_pct"]),
            step=0.01,
            key="lp_wide_spread_pct",
        )

        stress_spread = c3.number_input(
            "Stress Spread %",
            min_value=0.01,
            max_value=5.0,
            value=float(DEFAULT_LP_POLICY["stress_spread_pct"]),
            step=0.01,
            key="lp_stress_spread_pct",
        )

        d1, d2 = st.columns(2)

        min_volume = d1.number_input(
            "Minimum Volume",
            min_value=0,
            value=int(DEFAULT_LP_POLICY["minimum_volume"]),
            step=10,
            key="lp_minimum_volume",
        )

        min_oi = d2.number_input(
            "Minimum Open Interest",
            min_value=0,
            value=int(DEFAULT_LP_POLICY["minimum_open_interest"]),
            step=50,
            key="lp_minimum_open_interest",
        )

    policy = dict(DEFAULT_LP_POLICY)
    policy.update({
        "tight_spread_pct": float(tight_spread),
        "wide_spread_pct": float(wide_spread),
        "stress_spread_pct": float(stress_spread),
        "minimum_volume": float(min_volume),
        "minimum_open_interest": float(min_oi),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_liquidity_provider_report(
        chain_data=chain_data,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No liquidity provider data available."))
        return report

    summary = report.get("summary", {})
    regime = report.get("regime", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Liquidity Regime", summary.get("liquidity_regime", "—"))
    c2.metric("Avg Score", f"{summary.get('avg_liquidity_score', 0)}/100")
    c3.metric("Avg Spread", f"{summary.get('avg_spread_pct', 0):.4f}")
    c4.metric("Contracts", summary.get("contract_count", 0))

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Strong", summary.get("strong_count", 0))
    d2.metric("Watch", summary.get("watch_count", 0))
    d3.metric("Illiquid", summary.get("illiquid_count", 0))
    d4.metric("Stress", summary.get("stress_count", 0))

    st.markdown("#### Liquidity Provider Summary")
    st.info(summarize_liquidity_provider(report))

    drivers = regime.get("drivers", [])
    if drivers:
        st.markdown("#### Liquidity Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_recs, tab_opps, tab_chain, tab_expiry, tab_strike = st.tabs(
        [
            "Recommendations",
            "Opportunity / Risk Queue",
            "Contract Map",
            "By Expiry",
            "By Strike",
        ]
    )

    with tab_recs:
        _table(report.get("recommendations"))

    with tab_opps:
        _table(report.get("opportunities"))

    with tab_chain:
        _table(
            (report.get("lp_map", {}) or {}).get("chain"),
            [
                "expiry",
                "dte",
                "type",
                "strike",
                "bid",
                "ask",
                "mid",
                "spread",
                "spread_pct",
                "volume",
                "open_interest",
                "Liquidity Provider Score",
                "Liquidity Quality",
                "Execution Guidance",
                "Liquidity Flags",
            ],
        )

    with tab_expiry:
        _table((report.get("lp_map", {}) or {}).get("by_expiry"))

    with tab_strike:
        _table((report.get("lp_map", {}) or {}).get("by_strike"))

    return report
