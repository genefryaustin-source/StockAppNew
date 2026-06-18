"""
Sprint 4 Phase 2 — Institutional Flow Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_flow_regime_engine import build_flow_regime_report, summarize_flow_regime


def _extract_flow_source(chain_data: dict[str, Any] | None) -> Any:
    if not chain_data:
        return {}
    for key in ("flows", "alerts", "unusual", "items", "rows", "contracts"):
        if key in chain_data:
            return chain_data[key]
    return chain_data.get("all_rows", chain_data)


def render_flow_intelligence_dashboard(ticker: str, chain_data: dict[str, Any] | None = None) -> dict[str, Any]:
    st.subheader(f"🌊 Institutional Flow Intelligence — {ticker.upper()}")
    st.caption("Flow classification · confidence · clustering · accumulation · regime detection")

    min_volume = st.slider(
        "Minimum contract volume",
        min_value=0,
        max_value=1000,
        value=100,
        step=50,
        key=f"flow_intel_min_volume_{ticker.upper()}",
    )

    source = _extract_flow_source(chain_data)
    report = build_flow_regime_report(source, min_volume=min_volume)

    if not report.get("available"):
        st.warning("No qualifying options flow available for the selected threshold.")
        return report

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Regime", report.get("regime", "—"))
    c2.metric("Bias", report.get("bias", "—"))
    c3.metric("Regime Score", f"{report.get('regime_score', 0)}/100")
    c4.metric("Confidence", report.get("confidence", {}).get("confidence_grade", "—"))

    st.markdown("#### Institutional Summary")
    st.markdown(f"- {summarize_flow_regime(report)}")
    for item in report.get("summary", []):
        st.markdown(f"- {item}")

    classification = report.get("classification", {})
    classified = classification.get("classified")
    if isinstance(classified, pd.DataFrame) and not classified.empty:
        with st.expander("Classified Flow", expanded=False):
            show_cols = [c for c in ["expiry", "strike", "type", "volume", "open_interest", "premium", "vol_oi_ratio", "flow_class"] if c in classified.columns]
            st.dataframe(classified[show_cols].head(200), use_container_width=True, hide_index=True)

    clusters = report.get("clusters", {})
    with st.expander("Flow Clusters", expanded=False):
        by_strike = clusters.get("by_strike")
        if isinstance(by_strike, pd.DataFrame) and not by_strike.empty:
            st.dataframe(by_strike, use_container_width=True, hide_index=True)
        else:
            st.caption("No flow clusters available.")

    with st.expander("Flow Class Summary", expanded=False):
        by_class = clusters.get("by_class")
        if isinstance(by_class, pd.DataFrame) and not by_class.empty:
            st.dataframe(by_class, use_container_width=True, hide_index=True)
        else:
            st.caption("No class summary available.")

    return report
