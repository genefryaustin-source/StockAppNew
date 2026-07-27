from __future__ import annotations

import streamlit as st

from modules.trading_intelligence.recommendation_performance_engine import (
    RecommendationPerformanceEngine,
)


def _fmt_money(v):

    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_pct(v):

    try:
        return f"{float(v):,.2f}%"
    except Exception:
        return "0.00%"


def render_recommendation_performance_ui(
    db,
    portfolio_id: str,
):

    st.subheader(
        "📈 Recommendation Performance Analytics"
    )

    engine = RecommendationPerformanceEngine(
        db
    )

    try:

        summary = engine.build_summary(
            portfolio_id
        )

        breakdown = engine.recommendation_breakdown(
            portfolio_id
        )

        conviction = engine.conviction_analysis(
            portfolio_id
        )

        signals = engine.signal_effectiveness(
            portfolio_id
        )

        sectors = engine.sector_analysis(
            portfolio_id
        )

    except Exception as e:

        st.error(
            f"Performance analytics failed: {e}"
        )
        return

    # =====================================================
    # SUMMARY
    # =====================================================

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric(
        "Recommendations",
        summary.total_recommendations,
    )

    m2.metric(
        "Executed",
        summary.executed_recommendations,
    )

    m3.metric(
        "Execution Rate",
        _fmt_pct(
            summary.execution_rate
        ),
    )

    m4.metric(
        "Win Rate",
        _fmt_pct(
            summary.win_rate
        ),
    )

    m5.metric(
        "Total P&L",
        _fmt_money(
            summary.total_net_pnl
        ),
    )

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Recommendation Breakdown",
        "Conviction Analysis",
        "Signal Effectiveness",
        "Sector Effectiveness",
    ])

    # =====================================================
    # BREAKDOWN
    # =====================================================

    with tab1:

        st.markdown(
            "### Recommendation Distribution"
        )

        st.dataframe(
            breakdown,
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================
    # CONVICTION
    # =====================================================

    with tab2:

        st.markdown(
            "### Conviction Score Analysis"
        )

        st.dataframe(
            conviction,
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================
    # SIGNALS
    # =====================================================

    with tab3:

        st.markdown(
            "### Signal Effectiveness"
        )

        st.dataframe(
            signals,
            use_container_width=True,
            hide_index=True,
        )

    # =====================================================
    # SECTORS
    # =====================================================

    with tab4:

        st.markdown(
            "### Sector Effectiveness"
        )

        st.dataframe(
            sectors,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    with st.expander(
        "Performance Diagnostics",
        expanded=False,
    ):

        st.write(
            summary.to_dict()
        )