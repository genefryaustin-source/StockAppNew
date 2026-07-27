from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.recommendation_autopilot_engine import (
    RecommendationAutopilotEngine,
)


def render_recommendation_autopilot_dashboard(
    db,
    portfolio_id=None,
):
    st.subheader("🤖 Recommendation Autopilot")
    st.caption(
        "Reviews targets, stops, alerts, risk, and lifecycle data to recommend trade-management actions. "
        "This does not execute trades automatically."
    )

    engine = RecommendationAutopilotEngine(db)

    if st.button(
        "Refresh Autopilot",
        key="refresh_recommendation_autopilot",
    ):
        st.rerun()

    try:
        summary = engine.build_autopilot_summary(portfolio_id)
        actions = engine.generate_actions(portfolio_id)
    except Exception as e:
        st.error(f"Recommendation Autopilot failed: {e}")
        return

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Actions", summary.get("actions", 0))
    c2.metric("Critical", summary.get("critical", 0))
    c3.metric("High", summary.get("high", 0))
    c4.metric("Medium", summary.get("medium", 0))
    c5.metric("Status", summary.get("autopilot_status", "Clear"))

    top_action = summary.get("top_action", "None")

    if summary.get("critical", 0) > 0:
        st.error(f"Top action: {top_action}")
    elif summary.get("high", 0) > 0:
        st.warning(f"Top action: {top_action}")
    elif summary.get("actions", 0) > 0:
        st.info(f"Top action: {top_action}")
    else:
        st.success("No autopilot actions required.")

    st.divider()

    if actions.empty:
        st.success("Autopilot has no recommended actions.")
    else:
        priority_filter = st.multiselect(
            "Priority Filter",
            options=["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
            default=["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"],
            key="autopilot_priority_filter",
        )

        filtered = actions[
            actions["priority"].isin(priority_filter)
        ].copy()

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        symbols = filtered["symbol"].dropna().astype(str).unique().tolist()

        if symbols:
            selected_symbol = st.selectbox(
                "Action Detail",
                options=symbols,
                key="autopilot_action_detail_symbol",
            )

            detail = filtered[
                filtered["symbol"].astype(str) == selected_symbol
            ]

            if not detail.empty:
                row = detail.iloc[0].to_dict()

                st.markdown(f"### {row.get('title')}")
                st.write(row.get("rationale", ""))
                st.info(row.get("suggested_action", ""))

                d1, d2, d3 = st.columns(3)
                d1.metric("Priority", row.get("priority", "—"))
                d2.metric("Confidence", f"{float(row.get('confidence', 0)):,.1f}")
                d3.metric("Action Type", row.get("action_type", "—"))

    st.divider()

    with st.expander("Autopilot Diagnostics", expanded=False):
        test = engine.self_test(portfolio_id)

        if test.get("success"):
            st.success("Autopilot validation passed.")
            st.json(test)
        else:
            st.error(test.get("error", "Unknown error"))