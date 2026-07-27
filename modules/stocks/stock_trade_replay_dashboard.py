"""
modules/stocks/stock_trade_replay_dashboard.py

Institutional Trade Replay Dashboard

Provides a complete replay of a trade using the immutable
execution event stream.

Displays:

    • Trade Summary
    • Execution Timeline
    • Event Details
    • AI Review
    • Attribution
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

from modules.stocks.stock_execution_audit_service import (
    get_stock_execution_audit_service,
)


# ==========================================================
# Helpers
# ==========================================================

def _show_dataframe(title, rows):

    st.subheader(title)

    if not rows:

        st.info("No records available.")

        return

    df = pd.DataFrame(rows)

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,

    )


def _timeline(events):

    if not events:

        st.info("No execution events available.")

        return

    for event in events:

        timestamp = event.get(
            "event_timestamp",
            event.get("timestamp", ""),
        )

        st.markdown(

            f"""
**{event.get('event_type','')}**

**Time:** {timestamp}

**Status:** {event.get('status','')}

**Broker:** {event.get('broker','')}

---
"""
        )


# ==========================================================
# Dashboard
# ==========================================================

def render_stock_trade_replay_dashboard(

    db,

):

    dashboard_service = (

        get_stock_execution_dashboard_service(
            db,
        )

    )

    audit_service = (

        get_stock_execution_audit_service(
            db,
        )

    )

    st.title(

        "Trade Replay"

    )

    st.caption(

        "Institutional Order & Position Replay"

    )

    dashboard = dashboard_service.dashboard()

    events = dashboard["recent_events"]

    if not events:

        st.info(

            "No execution history available."

        )

        return

    #
    # Build selector
    #

    options = []

    lookup = {}

    for row in events:

        order_id = row.get("order_id")

        symbol = row.get("symbol", "")

        event = row.get("event_type", "")

        label = (

            f"{order_id} | "

            f"{symbol} | "

            f"{event}"

        )

        lookup[label] = order_id

        options.append(label)

    selected = st.selectbox(

        "Trade",

        options,

    )

    order_id = lookup[selected]

    replay = audit_service.build_trade_replay(

        order_id=order_id,

    )

    timeline = replay["timeline"]

    #
    # Summary
    #

    st.subheader(

        "Trade Summary"

    )

    first = replay.get("first_event")

    last = replay.get("last_event")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(

        "Events",

        replay["event_count"],

    )

    c2.metric(

        "Order",

        order_id,

    )

    c3.metric(

        "Symbol",

        first.get("symbol", "")

        if first

        else "",

    )

    c4.metric(

        "Final Status",

        last.get("status", "")

        if last

        else "",

    )

    st.divider()

    #
    # Workspace
    #

    tabs = st.tabs(

        [

            "Replay",

            "Timeline",

            "Audit",

            "Attribution",

            "AI Review",

        ]

    )

    # ======================================================
    # Replay
    # ======================================================

    with tabs[0]:

        st.subheader(

            "Execution Replay"

        )

        _timeline(

            timeline,

        )

    # ======================================================
    # Timeline
    # ======================================================

    with tabs[1]:

        _show_dataframe(

            "Execution Timeline",

            timeline,

        )

    # ======================================================
    # Audit
    # ======================================================

    with tabs[2]:

        audit = audit_service.get_audit_records(

            order_id=order_id,

            limit=500,

        )

        _show_dataframe(

            "Audit Trail",

            audit,

        )

    # ======================================================
    # Attribution
    # ======================================================

    with tabs[3]:

        attribution = [

            x

            for x in dashboard[
                "recent_attribution"
            ]

            if x.get("order_id") == order_id

        ]

        _show_dataframe(

            "Trade Attribution",

            attribution,

        )

    # ======================================================
    # AI Review
    # ======================================================

    with tabs[4]:

        reviews = [

            x

            for x in dashboard[
                "recent_reviews"
            ]

            if x.get("order_id") == order_id

        ]

        _show_dataframe(

            "AI Trade Review",

            reviews,

        )