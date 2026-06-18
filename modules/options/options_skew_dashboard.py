
"""
Sprint 10 Phase 4 — Skew Intelligence Dashboard
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_skew_engine import (
    build_skew_intelligence_report,
    summarize_skew_intelligence,
)


def render_skew_dashboard(
    ticker="",
    paper=True,
    chain_data=None,
):
    st.subheader("⚡ Skew Intelligence")
    st.caption(
        "Put skew · Call skew · Risk reversals · Skew opportunities"
    )

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)

        if isinstance(payload, dict) and "data" in payload:
            chain_data = payload["data"]
        else:
            chain_data = payload

    if chain_data is None or (
        isinstance(chain_data, pd.DataFrame)
        and chain_data.empty
    ):
        chain_data = get_options_chain(ticker)

    report = build_skew_intelligence_report(chain_data)

    if not report.get("available"):
        st.info(report.get("reason"))
        return report

    summary = report["summary"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Regime", summary["regime"])
    c2.metric("Put Skew", summary["put_skew"])
    c3.metric("Call Skew", summary["call_skew"])
    c4.metric("Risk Reversal", summary["risk_reversal"])

    st.info(summarize_skew_intelligence(report))

    tabs = st.tabs([
        "Skew Curve",
        "State",
        "Opportunities",
    ])

    with tabs[0]:
        st.dataframe(
            report["skew_curve"],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[1]:
        st.json(report["state"])

    with tabs[2]:
        st.dataframe(
            report["opportunities"],
            use_container_width=True,
            hide_index=True,
        )

    return report
