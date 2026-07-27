from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.recommendation_lifecycle_engine import (
    RecommendationLifecycleEngine,
)


def render_recommendation_lifecycle_dashboard(
    db,
    portfolio_id=None,
):

    st.subheader("🔄 Recommendation Lifecycle Dashboard")

    engine = RecommendationLifecycleEngine(db)

    summary = engine.generate_lifecycle_summary(
        portfolio_id=portfolio_id
    )

    metrics = engine.recommendation_funnel_metrics(
        portfolio_id=portfolio_id
    )

    lifecycle = engine.generate_lifecycle_view(
        portfolio_id=portfolio_id
    )

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Recommendations",
        metrics.get("total", 0),
    )

    c2.metric(
        "Executed",
        metrics.get("executed", 0),
    )

    c3.metric(
        "Execution Rate",
        f"{metrics.get('execution_rate', 0):,.1f}%",
    )

    c4.metric(
        "Open",
        metrics.get("open", 0),
    )

    c5.metric(
        "Expired",
        metrics.get("expired", 0),
    )

    st.divider()

    status_counts = summary.get(
        "status_counts",
        {},
    )

    if status_counts:

        chart_df = pd.DataFrame(
            [
                {
                    "Status": k,
                    "Count": v,
                }
                for k, v in status_counts.items()
            ]
        )

        st.subheader("Lifecycle Status Distribution")

        st.bar_chart(
            chart_df.set_index("Status")
        )

    st.divider()

    st.subheader("Recommendation Lifecycle Detail")

    if lifecycle.empty:

        st.info(
            "No recommendation lifecycle data available."
        )

    else:

        lifecycle = lifecycle.copy()

        lifecycle["age_days"] = (
            lifecycle["age_days"]
            .fillna(0)
            .round(1)
        )

        st.dataframe(
            lifecycle,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    status_filter = st.selectbox(
        "Filter Status",
        options=[
            "ALL",
            "OPEN",
            "EXECUTED",
            "TARGET_APPROACHING",
            "TARGET_HIT",
            "STOP_APPROACHING",
            "STOP_HIT",
            "EXPIRED",
        ],
        key="lifecycle_status_filter",
    )

    if (
        status_filter != "ALL"
        and not lifecycle.empty
    ):

        filtered = lifecycle[
            lifecycle["status"]
            == status_filter
        ]

        st.subheader(
            f"{status_filter} Recommendations"
        )

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )

    with st.expander(
        "Lifecycle Engine Self-Test",
        expanded=False,
    ):

        test = engine.self_test()

        if test.get("success"):

            st.success(
                "Lifecycle engine validation passed."
            )

            st.json(test)

        else:

            st.error(
                test.get(
                    "error",
                    "Unknown error",
                )
            )