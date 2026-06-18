
"""
Sprint 6 Phase 3 — Position Sizing Intelligence Dashboard
"""

from __future__ import annotations

import streamlit as st

from modules.options.options_position_sizing_engine import (
    calculate_position_size,
    build_position_sizing_matrix,
    classify_position_size,
)


def render_position_sizing_dashboard():

    st.subheader("📏 Position Sizing Intelligence")
    st.caption(
        "Risk budget allocation • Contract sizing • Capital preservation"
    )

    c1, c2, c3 = st.columns(3)

    portfolio_value = c1.number_input(
        "Portfolio Value ($)",
        value=100000.0,
        min_value=1000.0,
        step=1000.0,
    )

    risk_percent = c2.number_input(
        "Risk % Per Trade",
        value=1.0,
        min_value=0.1,
        max_value=10.0,
        step=0.1,
    )

    max_loss = c3.number_input(
        "Max Loss Per Contract ($)",
        value=250.0,
        min_value=1.0,
        step=10.0,
    )

    result = calculate_position_size(
        portfolio_value,
        risk_percent,
        max_loss,
    )

    m1, m2, m3, m4 = st.columns(4)

    m1.metric("Risk Budget", f"${result['risk_budget']:,.0f}")
    m2.metric("Contracts", result["recommended_contracts"])
    m3.metric("Capital At Risk", f"${result['capital_at_risk']:,.0f}")
    m4.metric(
        "Size Class",
        classify_position_size(result["recommended_contracts"])
    )

    st.markdown("### Position Sizing Matrix")

    matrix = build_position_sizing_matrix(
        portfolio_value,
        max_loss,
    )

    st.dataframe(
        matrix,
        use_container_width=True,
        hide_index=True,
    )
