"""
ui/admin/analytics_optimizer_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.analytics.autonomous_analytics_optimizer import (
    get_autonomous_analytics_optimizer,
)


def render_analytics_optimizer_dashboard():

    st.header(
        "Autonomous Analytics Optimizer"
    )

    optimizer = (
        get_autonomous_analytics_optimizer()
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "Analyze"
        ):

            analysis = (
                optimizer.analyze()
            )

            st.session_state[
                "analytics_analysis"
            ] = analysis

    with col2:

        if st.button(
            "Optimize"
        ):

            result = (
                optimizer.optimize()
            )

            st.session_state[
                "analytics_optimization"
            ] = result

    if (
        "analytics_analysis"
        in st.session_state
    ):

        analysis = st.session_state[
            "analytics_analysis"
        ]

        st.subheader(
            "Analysis"
        )

        st.json(
            analysis
        )

    if (
        "analytics_optimization"
        in st.session_state
    ):

        result = st.session_state[
            "analytics_optimization"
        ]

        st.subheader(
            "Optimization Result"
        )

        st.json(
            result
        )