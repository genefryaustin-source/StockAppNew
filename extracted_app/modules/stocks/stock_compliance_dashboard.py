"""
modules/stocks/stock_compliance_dashboard.py

Institutional Compliance Dashboard

Displays:

    • Regulatory Summary
    • Order Lifecycle
    • Position Lifecycle
    • Event Distribution
    • Audit History
    • Trade Replay Access

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

        st.info("No compliance data available.")

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

def render_stock_compliance_dashboard(

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

    compliance = dashboard["compliance"]

    audit = dashboard["audit"]

    st.title(

        "Execution Compliance"

    )

    st.caption(

        "Institutional Audit & Regulatory Compliance"

    )

    #
    # KPI Cards
    #

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        _metric(

            "Events",

            compliance.get(

                "events",

                0,

            ),

        )

    with c2:

        _metric(

            "Orders Filled",

            compliance.get(

                "orders_filled",

                0,

            ),

        )

    with c3:

        _metric(

            "Positions Closed",

            compliance.get(

                "positions_closed",

                0,

            ),

        )

    with c4:

        _metric(

            "Stop Losses",

            compliance.get(

                "stop_losses",

                0,

            ),

        )

    st.divider()

    tabs = st.tabs(

        [

            "Compliance",

            "Orders",

            "Positions",

            "Audit",

            "Replay",

        ]

    )

    # ======================================================
    # Compliance
    # ======================================================

    with tabs[0]:

        df = pd.DataFrame(

            [

                {

                    "Metric": key,

                    "Value": value,

                }

                for key, value in compliance.items()

            ]

        )

        st.dataframe(

            df,

            use_container_width=True,

            hide_index=True,

        )

    # ======================================================
    # Orders
    # ======================================================

    with tabs[1]:

        if audit:

            df = pd.DataFrame(audit)

            cols = [

                c

                for c in [

                    "event_timestamp",

                    "order_id",

                    "symbol",

                    "event_type",

                    "status",

                    "broker",

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

                "No order history."

            )

    # ======================================================
    # Positions
    # ======================================================

    with tabs[2]:

        if audit:

            df = pd.DataFrame(audit)

            cols = [

                c

                for c in [

                    "position_id",

                    "symbol",

                    "side",

                    "event_type",

                    "status",

                    "event_timestamp",

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

                "No position history."

            )

    # ======================================================
    # Audit Trail
    # ======================================================

    with tabs[3]:

        _show_dataframe(

            "Audit Trail",

            audit,

        )

    # ======================================================
    # Trade Replay
    # ======================================================

    with tabs[4]:

        if not audit:

            st.info(

                "No replay data available."

            )

        else:

            replay_rows = []

            for row in audit:

                replay_rows.append(

                    {

                        "Order":

                            row.get(

                                "order_id",

                            ),

                        "Position":

                            row.get(

                                "position_id",

                            ),

                        "Symbol":

                            row.get(

                                "symbol",

                            ),

                        "Event":

                            row.get(

                                "event_type",

                            ),

                        "Time":

                            row.get(

                                "event_timestamp",

                            ),

                    }

                )

            st.dataframe(

                pd.DataFrame(

                    replay_rows,

                ),

                use_container_width=True,

                hide_index=True,

            )

            st.info(

                "Selecting a row can be wired to "
                "render_stock_trade_replay_dashboard() "
                "to replay the complete execution lifecycle."

            )