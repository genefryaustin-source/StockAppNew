"""
modules/stocks/stock_execution_dashboard.py

Institutional Stock Execution Dashboard

Displays:

    • KPI Cards
    • Recent Execution Events
    • Trade Attribution
    • AI Trade Reviews
    • Compliance
    • Audit Trail

Requires:

    stock_execution_dashboard_service.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.stocks.stock_execution_dashboard_service import (
    get_stock_execution_dashboard_service,
)


# ==========================================================
# Helpers
# ==========================================================

def _metric_columns(cards):

    cols = st.columns(len(cards))

    for col, card in zip(cols, cards):

        value = card.get("value", 0)

        fmt = card.get("format")

        if fmt == "percent":

            display = f"{value:.2f}%"

        elif fmt == "currency":

            display = f"${value:,.2f}"

        else:

            display = value

        col.metric(

            card["title"],

            display,

            card.get("delta"),
        )


def _show_dataframe(title, rows):

    st.subheader(title)

    if not rows:

        st.info("No data available.")

        return

    df = pd.DataFrame(rows)

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,
    )


# ==========================================================
# Main Dashboard
# ==========================================================

def render_stock_execution_dashboard(

    db,

    *,

    portfolio_id=None,

):

    service = get_stock_execution_dashboard_service(
        db,
    )

    dashboard = service.dashboard(

        portfolio_id=portfolio_id,

    )

    st.title(
        "Execution Analytics"
    )

    st.markdown(
        "Institutional Execution Intelligence"
    )

    st.divider()

    #
    # KPI Cards
    #

    _metric_columns(

        dashboard["cards"]

    )

    st.divider()

    #
    # Workspace
    #

    tabs = st.tabs(

        [

            "Execution Events",

            "Trade Attribution",

            "AI Reviews",

            "Compliance",

            "Audit Trail",

        ]

    )

    # ======================================================
    # Execution Events
    # ======================================================

    with tabs[0]:

        summary = dashboard["event_summary"]

        cols = st.columns(4)

        cols[0].metric(

            "Events",

            summary.get(
                "total_events",
                0,
            ),
        )

        cols[1].metric(

            "Orders Filled",

            summary.get(
                "orders_filled",
                0,
            ),
        )

        cols[2].metric(

            "Positions Open",

            summary.get(
                "positions_opened",
                0,
            ),
        )

        cols[3].metric(

            "Positions Closed",

            summary.get(
                "positions_closed",
                0,
            ),
        )

        st.divider()

        _show_dataframe(

            "Recent Execution Events",

            dashboard["recent_events"],

        )

    # ======================================================
    # Attribution
    # ======================================================

    with tabs[1]:

        summary = dashboard["trade_attribution"]

        cols = st.columns(4)

        cols[0].metric(

            "Trades",

            summary.get(
                "trade_count",
                0,
            ),
        )

        cols[1].metric(

            "Average Score",

            f"{summary.get('average_score',0):.2f}",

        )

        cols[2].metric(

            "Average Return",

            f"{summary.get('average_return',0):.2f}%",

        )

        cols[3].metric(

            "Average P&L",

            f"${summary.get('average_pnl',0):,.2f}",

        )

        st.divider()

        _show_dataframe(

            "Trade Attribution",

            dashboard["recent_attribution"],

        )

    # ======================================================
    # AI Reviews
    # ======================================================

    with tabs[2]:

        summary = dashboard["ai_review"]

        cols = st.columns(3)

        cols[0].metric(

            "Reviews",

            summary.get(
                "review_count",
                0,
            ),
        )

        cols[1].metric(

            "Average Rating",

            f"{summary.get('average_rating',0):.2f}",

        )

        cols[2].metric(

            "Confidence",

            f"{summary.get('average_confidence',0):.2f}%",

        )

        st.divider()

        _show_dataframe(

            "AI Trade Reviews",

            dashboard["recent_reviews"],

        )

    # ======================================================
    # Compliance
    # ======================================================

    with tabs[3]:

        compliance = dashboard["compliance"]

        df = pd.DataFrame(

            [

                {

                    "Metric": k,

                    "Value": v,

                }

                for k, v in compliance.items()

            ]

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    # ======================================================
    # Audit
    # ======================================================

    with tabs[4]:

        _show_dataframe(

            "Execution Audit Trail",

            dashboard["audit"],

        )