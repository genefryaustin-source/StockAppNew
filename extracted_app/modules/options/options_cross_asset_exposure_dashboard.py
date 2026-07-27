
from __future__ import annotations
import streamlit as st
from modules.options.options_cross_asset_exposure_engine import (
    build_cross_asset_exposure_report,
    summarize_cross_asset_exposure,
)

def render_cross_asset_exposure_dashboard(positions=None):
    st.subheader("🌐 Cross-Asset Exposure Intelligence")

    report = build_cross_asset_exposure_report(positions or [])

    if not report.get("available"):
        st.info(report.get("reason"))
        return report

    c1,c2,c3 = st.columns(3)
    c1.metric("Total Exposure", f"${report['total_exposure']:,.0f}")
    c2.metric("Diversification", report["diversification_score"])
    c3.metric("Concentration", report["concentration_score"])

    st.info(summarize_cross_asset_exposure(report))
    st.dataframe(report["asset_exposure"], use_container_width=True)

    return report
