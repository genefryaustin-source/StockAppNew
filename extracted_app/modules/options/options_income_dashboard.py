"""
Sprint 8 Phase 3 — Income Generation Intelligence Dashboard
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import (
    load_portfolio_positions,
)

from modules.options.options_income_engine import (
    build_income_intelligence_report,
    summarize_income_intelligence,
)


def render_income_dashboard(
    ticker="",
    paper=True,
):
    st.subheader("💵 Income Generation Intelligence")

    with st.spinner(
        "Loading portfolio positions..."
    ):
        positions = load_portfolio_positions(
            ticker=ticker,
            paper=paper,
        )

    report = build_income_intelligence_report(
        positions
    )

    if not report.get("available"):
        st.info(
            report.get(
                "reason",
                "No data available."
            )
        )
        return

    summary = report["summary"]
    forecast = report["forecast"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Premium Income",
        f"${summary.get('total_premium',0):,.0f}"
    )

    c2.metric(
        "Monthly Yield",
        f"{summary.get('monthly_yield',0):.2f}%"
    )

    c3.metric(
        "Annual Yield",
        f"{summary.get('annualized_yield',0):.2f}%"
    )

    c4.metric(
        "Wheel Income",
        f"${summary.get('wheel_income',0):,.0f}"
    )

    st.info(
        summarize_income_intelligence(
            report
        )
    )

    tabs = st.tabs(
        [
            "Income Sources",
            "Forecast",
            "Opportunities",
        ]
    )

    with tabs[0]:

        st.markdown(
            "### Income Sources"
        )

        st.dataframe(
            report["positions"],
            use_container_width=True,
            hide_index=True,
        )

    with tabs[1]:

        st.markdown(
            "### Income Forecast"
        )

        forecast_df = pd.DataFrame(
            [
                {
                    "Period": "30 Day",
                    "Projected Income": forecast["30_day"],
                },
                {
                    "Period": "60 Day",
                    "Projected Income": forecast["60_day"],
                },
                {
                    "Period": "90 Day",
                    "Projected Income": forecast["90_day"],
                },
                {
                    "Period": "Annual",
                    "Projected Income": forecast["annual_projection"],
                },
            ]
        )

        st.dataframe(
            forecast_df,
            use_container_width=True,
            hide_index=True,
        )

    with tabs[2]:

        st.markdown(
            "### Income Opportunities"
        )

        st.dataframe(
            report["opportunities"],
            use_container_width=True,
            hide_index=True,
        )