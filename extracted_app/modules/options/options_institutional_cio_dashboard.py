
"""
Sprint 12 Phase 5 — Institutional Options CIO Dashboard
"""

from __future__ import annotations

import streamlit as st

from modules.options.options_institutional_cio_engine import (
    build_institutional_cio_report,
    summarize_cio_dashboard,
)


def render_institutional_options_cio_dashboard(
    ticker="",
    paper=True,
    portfolio_optimization_report=None,
    trade_selection_report=None,
    risk_rebalancing_report=None,
    auto_income_report=None,
    volatility_report=None,
    market_maker_report=None,
):

    st.subheader(
        "🏛 Institutional Options CIO Dashboard"
    )

    cache_key = (
        f"institutional_cio_{ticker}_{paper}"
    )

    if cache_key not in st.session_state:

        st.session_state[cache_key] = (
            build_institutional_cio_report(
                portfolio_optimization_report=
                portfolio_optimization_report,
                trade_selection_report=
                trade_selection_report,
                risk_rebalancing_report=
                risk_rebalancing_report,
                auto_income_report=
                auto_income_report,
                volatility_report=
                volatility_report,
                market_maker_report=
                market_maker_report,
            )
        )

    report = st.session_state[cache_key]

    st.success(
        summarize_cio_dashboard(report)
    )

    s = report["summary"]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "CIO Score",
        s["cio_score"],
    )

    c2.metric(
        "Optimization",
        s["optimization_score"],
    )

    c3.metric(
        "Trade Selection",
        s["trade_score"],
    )

    c4.metric(
        "Income",
        s["income_score"],
    )

    st.markdown(
        "### CIO Directives"
    )

    st.dataframe(
        report["directives"],
        use_container_width=True,
        hide_index=True,
    )

    return report
