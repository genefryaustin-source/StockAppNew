"""
modules/stocks/stock_ai_trade_review_dashboard.py

Institutional AI Trade Review Dashboard

Displays:

    • AI Performance KPIs
    • Institutional Ratings
    • Trade Coaching
    • Recommendations
    • Strengths
    • Weaknesses
    • Confidence Analytics

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

def _metric(title, value):

    st.metric(
        title,
        value,
    )


def _show_dataframe(
    title,
    rows,
):

    st.subheader(title)

    if not rows:

        st.info("No AI reviews available.")

        return

    df = pd.DataFrame(rows)

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,

    )


def _display_list(
    values,
    icon,
):

    if not values:

        st.info("None")

        return

    if isinstance(values, str):

        values = values.splitlines()

    for item in values:

        if item:

            st.markdown(f"{icon} {item}")


# ==========================================================
# Dashboard
# ==========================================================

def render_stock_ai_trade_review_dashboard(

    db,

    *,

    portfolio_id=None,

):

    dashboard_service = (

        get_stock_execution_dashboard_service(
            db,
        )

    )

    dashboard = dashboard_service.dashboard(

        portfolio_id=portfolio_id,

    )

    summary = dashboard["ai_review"]

    reviews = dashboard["recent_reviews"]

    st.title(

        "AI Trade Review"

    )

    st.caption(

        "Institutional AI Trading Coach"

    )

    #
    # KPI Cards
    #

    c1, c2, c3 = st.columns(3)

    with c1:

        _metric(

            "Reviews",

            summary.get(

                "review_count",

                0,

            ),

        )

    with c2:

        _metric(

            "Average Rating",

            f"{summary.get('average_rating',0):.2f}",

        )

    with c3:

        _metric(

            "Confidence",

            f"{summary.get('average_confidence',0):.2f}%",

        )

    st.divider()

    tabs = st.tabs(

        [

            "Reviews",

            "Coaching",

            "Recommendations",

            "Strengths",

            "Weaknesses",

        ]

    )

    # ======================================================
    # Reviews
    # ======================================================

    with tabs[0]:

        _show_dataframe(

            "AI Reviews",

            reviews,

        )

    # ======================================================
    # Coaching
    # ======================================================

    with tabs[1]:

        if not reviews:

            st.info(

                "No AI coaching available."

            )

        else:

            for review in reviews:

                symbol = review.get(

                    "symbol",

                    "",

                )

                rating = review.get(

                    "overall_rating",

                    0,

                )

                confidence = review.get(

                    "confidence",

                    0,

                )

                summary_text = review.get(

                    "summary",

                    "",

                )

                st.subheader(symbol)

                c1, c2 = st.columns(2)

                c1.metric(

                    "Rating",

                    f"{rating:.2f}",

                )

                c2.metric(

                    "Confidence",

                    f"{confidence:.2f}%",

                )

                st.info(summary_text)

                st.divider()

    # ======================================================
    # Recommendations
    # ======================================================

    with tabs[2]:

        if not reviews:

            st.info(

                "No recommendations."

            )

        else:

            for review in reviews:

                st.markdown(

                    f"### {review.get('symbol','')}"

                )

                _display_list(

                    review.get(

                        "recommendations",

                        "",

                    ),

                    "✅",

                )

                st.divider()

    # ======================================================
    # Strengths
    # ======================================================

    with tabs[3]:

        if not reviews:

            st.info(

                "No strengths identified."

            )

        else:

            for review in reviews:

                st.markdown(

                    f"### {review.get('symbol','')}"

                )

                _display_list(

                    review.get(

                        "strengths",

                        "",

                    ),

                    "🟢",

                )

                st.divider()

    # ======================================================
    # Weaknesses
    # ======================================================

    with tabs[4]:

        if not reviews:

            st.info(

                "No weaknesses identified."

            )

        else:

            for review in reviews:

                st.markdown(

                    f"### {review.get('symbol','')}"

                )

                _display_list(

                    review.get(

                        "weaknesses",

                        "",

                    ),

                    "🔴",

                )

                st.divider()