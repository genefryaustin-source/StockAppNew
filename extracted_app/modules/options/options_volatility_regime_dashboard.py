"""
Sprint 10 Phase 2 — Volatility Regime Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_volatility_regime_engine import (
    DEFAULT_VOL_REGIME_POLICY,
    build_volatility_regime_report,
    summarize_volatility_regime,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_volatility_regime_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("📡 Volatility Regime Intelligence")
    st.caption("IV Rank · IV Percentile · IV vs RV proxy · Volatility Risk Premium · Regime transition")

    with st.expander("Regime Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        low_iv = c1.number_input(
            "Low IV Threshold",
            min_value=0.01,
            max_value=3.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["low_iv"]),
            step=0.01,
            key="vol_regime_low_iv",
        )

        elevated_iv = c2.number_input(
            "Elevated IV Threshold",
            min_value=0.01,
            max_value=3.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["elevated_iv"]),
            step=0.01,
            key="vol_regime_elevated_iv",
        )

        high_iv = c3.number_input(
            "High IV Threshold",
            min_value=0.01,
            max_value=3.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["high_iv"]),
            step=0.01,
            key="vol_regime_high_iv",
        )

        d1, d2, d3 = st.columns(3)

        crisis_iv = d1.number_input(
            "Crisis IV Threshold",
            min_value=0.01,
            max_value=5.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["crisis_iv"]),
            step=0.01,
            key="vol_regime_crisis_iv",
        )

        vrp_pos = d2.number_input(
            "Positive VRP Threshold",
            min_value=0.0,
            max_value=1.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["vrp_positive_threshold"]),
            step=0.01,
            key="vol_regime_vrp_pos",
        )

        vrp_neg = d3.number_input(
            "Negative VRP Threshold",
            min_value=-1.0,
            max_value=0.0,
            value=float(DEFAULT_VOL_REGIME_POLICY["vrp_negative_threshold"]),
            step=0.01,
            key="vol_regime_vrp_neg",
        )

    policy = dict(DEFAULT_VOL_REGIME_POLICY)
    policy.update({
        "low_iv": float(low_iv),
        "elevated_iv": float(elevated_iv),
        "high_iv": float(high_iv),
        "crisis_iv": float(crisis_iv),
        "vrp_positive_threshold": float(vrp_pos),
        "vrp_negative_threshold": float(vrp_neg),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_volatility_regime_report(
        chain_data=chain_data,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No volatility regime data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Current Regime", summary.get("current_regime", "—"))
    c2.metric("Avg IV", f"{summary.get('avg_iv', 0):.4f}")
    c3.metric("IV Rank", f"{summary.get('iv_rank', 0)}")
    c4.metric("IV Percentile", f"{summary.get('iv_percentile', 0)}")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Realized Vol Proxy", f"{summary.get('realized_vol_proxy', 0):.4f}")
    d2.metric("IV-RV Spread", f"{summary.get('iv_rv_spread', 0):.4f}")
    d3.metric("VRP", summary.get("volatility_risk_premium", "—"))
    d4.metric("Stability", f"{summary.get('stability_score', 0)}/100")

    st.markdown("#### Volatility Regime Summary")
    st.info(summarize_volatility_regime(report))

    tab_recs, tab_expiry, tab_vrp, tab_transition, tab_chain = st.tabs(
        [
            "Trade Recommendations",
            "Regime by Expiry",
            "IV vs RV / VRP",
            "Transition / Persistence",
            "Chain Diagnostics",
        ]
    )

    with tab_recs:
        _table(report.get("recommendations"))

    with tab_expiry:
        _table(report.get("by_expiry"))

    with tab_vrp:
        st.json(report.get("vrp", {}))

    with tab_transition:
        st.markdown("##### Transition")
        st.json(report.get("transition", {}))
        st.markdown("##### Persistence")
        st.json(report.get("persistence", {}))

    with tab_chain:
        _table(
            report.get("chain"),
            [
                "expiry",
                "dte",
                "type",
                "strike",
                "iv",
                "mid",
                "volume",
                "open_interest",
                "delta",
                "gamma",
                "theta",
                "vega",
            ],
        )

    return report
