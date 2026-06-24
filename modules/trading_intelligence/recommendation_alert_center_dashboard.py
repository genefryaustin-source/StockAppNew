from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.recommendation_alert_center import (
    RecommendationAlertCenter,
)


def render_recommendation_alert_center_dashboard(
    db,
    portfolio_id=None,
):

    st.subheader("🚨 Recommendation Alert Center")

    center = RecommendationAlertCenter(db)

    center.ensure_schema()

    refresh_col, persist_col = st.columns([1, 1])

    persist_alerts = persist_col.checkbox(
        "Persist Alerts",
        value=False,
        key="persist_alerts_checkbox",
    )

    if refresh_col.button(
        "Refresh Alerts",
        key="refresh_recommendation_alerts",
    ):
        st.rerun()

    alerts = center.get_active_alerts(
        portfolio_id=portfolio_id,
        persist=persist_alerts,
    )

    counts = center.get_alert_counts(
        portfolio_id=portfolio_id,
    )

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric(
        "Total",
        counts.get("total", 0),
    )

    c2.metric(
        "Critical",
        counts.get("critical", 0),
    )

    c3.metric(
        "High",
        counts.get("high", 0),
    )

    c4.metric(
        "Medium",
        counts.get("medium", 0),
    )

    c5.metric(
        "Low",
        counts.get("low", 0),
    )

    c6.metric(
        "Info",
        counts.get("info", 0),
    )

    st.divider()

    if alerts.empty:

        st.success(
            "No active recommendation alerts."
        )

    else:

        severity_filter = st.multiselect(
            "Severity Filter",
            options=[
                "CRITICAL",
                "HIGH",
                "MEDIUM",
                "LOW",
                "INFO",
            ],
            default=[
                "CRITICAL",
                "HIGH",
                "MEDIUM",
                "LOW",
                "INFO",
            ],
            key="alert_severity_filter",
        )

        filtered = alerts[
            alerts["severity"].isin(
                severity_filter
            )
        ]

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    st.subheader("Persisted Alert Repository")

    persisted = center.load_persisted_alerts(
        portfolio_id=portfolio_id,
        include_resolved=False,
        limit=500,
    )

    if persisted.empty:

        st.info(
            "No persisted alerts."
        )

    else:

        st.dataframe(
            persisted,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        selected_alert = st.selectbox(
            "Alert ID",
            options=persisted["id"].tolist(),
            key="selected_alert_id",
        )

        a1, a2 = st.columns(2)

        if a1.button(
            "Acknowledge Alert",
            key="ack_alert_btn",
        ):

            center.acknowledge_alert(
                selected_alert
            )

            st.success(
                "Alert acknowledged."
            )

            st.rerun()

        if a2.button(
            "Resolve Alert",
            key="resolve_alert_btn",
        ):

            center.resolve_alert(
                selected_alert
            )

            st.success(
                "Alert resolved."
            )

            st.rerun()

    st.divider()

    st.subheader("Alert Summary")

    summary = center.generate_alert_summary(
        portfolio_id=portfolio_id,
    )

    st.json(summary)

    with st.expander(
        "Alert Center Self-Test",
        expanded=False,
    ):

        test = center.self_test(
            portfolio_id=portfolio_id,
        )

        if test.get("success"):

            st.success(
                "Alert center validation passed."
            )

            st.json(test)

        else:

            st.error(
                test.get(
                    "error",
                    "Unknown error",
                )
            )