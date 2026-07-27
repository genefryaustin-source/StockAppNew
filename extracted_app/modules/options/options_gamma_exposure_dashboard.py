from __future__ import annotations
import streamlit as st
from modules.options.options_gamma_exposure_engine import (
    build_gamma_exposure_report,
    summarize_gamma_exposure,
)

def render_gamma_exposure_dashboard(ticker="", paper=True, chain_data=None):
    st.subheader("⚛ Gamma Exposure Intelligence")

    report = build_gamma_exposure_report(chain_data)

    if not report.get("available"):
        st.info(report.get("reason"))
        return report

    s = report["summary"]

    c1,c2,c3 = st.columns(3)
    c1.metric("Gamma Regime", s["gamma_regime"])
    c2.metric("Net Gamma", f"{s['net_gamma']:,.0f}")
    c3.metric("Gamma Flip", s["gamma_flip"])

    st.info(summarize_gamma_exposure(report))

    st.dataframe(report["strike_gex"], use_container_width=True, hide_index=True)
    return report
