"""
ui/admin/analytics_governor_dashboard.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.analytics.analytics_resource_governor import (
    get_analytics_resource_governor,
)


def render_analytics_governor_dashboard():

    st.header(
        "Analytics Resource Governor"
    )

    governor = (
        get_analytics_resource_governor()
    )

    snapshot = governor.snapshot()

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Successes",
            snapshot["successes"],
        )

    with c2:
        st.metric(
            "Failures",
            snapshot["failures"],
        )

    with c3:
        st.metric(
            "Running Jobs",
            snapshot["running_jobs"],
        )

    with c4:
        st.metric(
            "Max Concurrency",
            snapshot["max_concurrent_jobs"],
        )

    st.subheader(
        "Governor State"
    )

    st.dataframe(
        pd.DataFrame(
            [snapshot]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader(
        "Governor Controls"
    )

    col1, col2 = st.columns(2)

    with col1:

        new_limit = st.number_input(
            "Max Concurrent Jobs",
            min_value=1,
            max_value=128,
            value=snapshot[
                "max_concurrent_jobs"
            ],
        )

    with col2:

        if st.button(
            "Apply Governor Settings"
        ):

            governor.state.max_concurrent_jobs = (
                int(new_limit)
            )

            st.success(
                "Governor updated."
            )