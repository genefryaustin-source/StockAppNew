
"""
Sprint 12 Phase 4 — Autonomous Income Management Dashboard
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_autonomous_income_management import (
    build_autonomous_income_management_report,
    summarize_autonomous_income_management,
)


def render_autonomous_income_management_dashboard(
    ticker="",
    paper=True,
    covered_call_report=None,
    csp_report=None,
    wheel_report=None,
    income_report=None,
):

    st.subheader("💰 Autonomous Income Management")

    cache_key = f"auto_income_{ticker}_{paper}"

    if cache_key not in st.session_state:

        st.session_state[cache_key] = (
            build_autonomous_income_management_report(
                covered_call_report=covered_call_report,
                csp_report=csp_report,
                wheel_report=wheel_report,
                income_report=income_report,
            )
        )

    report = st.session_state[cache_key]

    st.info(
        summarize_autonomous_income_management(report)
    )

    summary = report["summary"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Income Score",
        summary["income_score"]
    )

    c2.metric(
        "Rating",
        summary["income_rating"]
    )

    c3.metric(
        "Sources",
        summary["income_sources"]
    )

    c4.metric(
        "Actions",
        summary["action_count"]
    )

    tab1, tab2 = st.tabs([
        "Income Sources",
        "Action Queue",
    ])

    with tab1:
        st.dataframe(
            report["sources"],
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        st.dataframe(
            report["queue"],
            use_container_width=True,
            hide_index=True,
        )

    return report
