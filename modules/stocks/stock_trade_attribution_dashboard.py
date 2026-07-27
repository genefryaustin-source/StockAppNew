"""
modules/stocks/stock_trade_attribution_dashboard.py

Institutional Trade Attribution Dashboard

Displays:

    • Attribution KPIs
    • Trade Grades
    • Execution Scores
    • Risk Scores
    • Timing Scores
    • Strategy Scores
    • Strengths & Weaknesses

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

        st.info("No attribution records available.")

        return

    df = pd.DataFrame(rows)

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,

    )


# ==========================================================
# Dashboard
# ==========================================================

def render_stock_trade_attribution_dashboard(

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

    summary = dashboard["trade_attribution"]

    records = dashboard["recent_attribution"]

    st.title(

        "Trade Attribution"

    )

    st.caption(

        "Institutional Trade Performance Analysis"

    )

    #
    # KPI Cards
    #

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        _metric(

            "Trades",

            summary.get(

                "trade_count",

                0,

            ),

        )

    with c2:

        _metric(

            "Average Score",

            f"{summary.get('average_score',0):.2f}",

        )

    with c3:

        _metric(

            "Average Return",

            f"{summary.get('average_return',0):.2f}%",

        )

    with c4:

        _metric(

            "Average P&L",

            f"${summary.get('average_pnl',0):,.2f}",

        )

    st.divider()

    #
    # Workspace
    #

    tabs = st.tabs(

        [

            "Trades",

            "Grades",

            "Execution",

            "Risk",

            "Strengths",

        ]

    )

    # ======================================================
    # Trades
    # ======================================================

    with tabs[0]:

        _show_dataframe(

            "Trade Attribution",

            records,

        )

    # ======================================================
    # Grades
    # ======================================================

    with tabs[1]:

        grades = summary.get(

            "grades",

            {},

        )

        if not grades:

            st.info(

                "No grades available."

            )

        else:

            df = pd.DataFrame(

                [

                    {

                        "Grade": k,

                        "Trades": v,

                    }

                    for k, v in grades.items()

                ]

            )

            st.dataframe(

                df,

                use_container_width=True,

                hide_index=True,

            )

    # ======================================================
    # Execution
    # ======================================================

    with tabs[2]:

        if records:

            df = pd.DataFrame(records)

            cols = [

                c

                for c in [

                    "symbol",

                    "execution_score",

                    "timing_score",

                    "strategy_score",

                    "overall_score",

                ]

                if c in df.columns

            ]

            st.dataframe(

                df[cols],

                use_container_width=True,

                hide_index=True,

            )

        else:

            st.info(

                "No execution data available."

            )

    # ======================================================
    # Risk
    # ======================================================

    with tabs[3]:

        if records:

            df = pd.DataFrame(records)

            cols = [

                c

                for c in [

                    "symbol",

                    "risk_score",

                    "return_pct",

                    "realized_pnl",

                    "holding_minutes",

                ]

                if c in df.columns

            ]

            st.dataframe(

                df[cols],

                use_container_width=True,

                hide_index=True,

            )

        else:

            st.info(

                "No risk analytics available."

            )

    # ======================================================
    # Strengths / Weaknesses
    # ======================================================

    with tabs[4]:

        if not records:

            st.info(

                "No attribution analysis available."

            )

        else:

            for trade in records:

                symbol = trade.get(

                    "symbol",

                    "",

                )

                st.markdown(

                    f"### {symbol}"

                )

                col1, col2 = st.columns(2)

                with col1:

                    st.markdown(

                        "**Strengths**"

                    )

                    strengths = trade.get(

                        "strengths",

                        "",

                    )

                    if strengths:

                        if isinstance(

                            strengths,

                            str,

                        ):

                            for line in strengths.splitlines():

                                st.success(line)

                        else:

                            for line in strengths:

                                st.success(line)

                    else:

                        st.info(

                            "None"

                        )

                with col2:

                    st.markdown(

                        "**Weaknesses**"

                    )

                    weaknesses = trade.get(

                        "weaknesses",

                        "",

                    )

                    if weaknesses:

                        if isinstance(

                            weaknesses,

                            str,

                        ):

                            for line in weaknesses.splitlines():

                                st.warning(line)

                        else:

                            for line in weaknesses:

                                st.warning(line)

                    else:

                        st.info(

                            "None"

                        )

                st.divider()