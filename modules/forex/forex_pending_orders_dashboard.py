"""
modules/forex/forex_pending_orders_dashboard.py

Sprint FX-1

Forex Pending Orders Dashboard

Institutional pending order workstation.

Features
--------
• View all pending Forex orders
• Filter by account / pair / side / status
• Modify pending orders
• Cancel pending orders
• Paper Broker "Fill Now"
• Auto refresh
• Execution Event integration
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from modules.execution.execution_service import (
    get_execution_service,
)

from modules.execution.execution_order_repository import (
    ExecutionOrderRepository,
)

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
)


# ==============================================================================
# Helpers
# ==============================================================================

PENDING_STATUSES = {

    "NEW",

    "VALIDATED",

    "ACCEPTED",

    "PENDING",

    "PARTIALLY_FILLED",

}


# ==============================================================================
# Dashboard
# ==============================================================================


def render_forex_pending_orders_dashboard(
    *,
    db,
    portfolio_engine,
    account=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):

    st.title("📑 Pending Forex Orders")

    service = get_execution_service(

        db=db,

        portfolio_engine=portfolio_engine,

    )

    repo = ExecutionOrderRepository(
        db=db,
    )

    explorer = get_execution_event_explorer(
        db=db,
    )

    # ----------------------------------------------------------------------
    # Toolbar
    # ----------------------------------------------------------------------

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:

        pair_filter = st.text_input(
            "Pair Filter",
        ).upper()

    with c2:

        side_filter = st.selectbox(

            "Side",

            [

                "ALL",

                "BUY",

                "SELL",

            ],

        )

    with c3:

        if st.button(
            "Refresh",
            use_container_width=True,
        ):
            st.rerun()

    st.divider()

    # ----------------------------------------------------------------------
    # Load Orders
    # ----------------------------------------------------------------------

    orders = repo.load_pending_orders(

        account_id=getattr(
            account,
            "id",
            None,
        ),

        portfolio_id=portfolio_id,

    )

    rows = []

    for order in orders:

        if (
            pair_filter
            and pair_filter
            not in str(
                order.get(
                    "symbol",
                    "",
                )
            ).upper()
        ):
            continue

        if (
            side_filter != "ALL"
            and order.get("side") != side_filter
        ):
            continue

        rows.append(order)

    if not rows:

        st.info(
            "No pending orders."
        )

        return

    df = pd.DataFrame(rows)

    display_cols = [

        c

        for c in [

            "broker_order_id",

            "symbol",

            "side",

            "order_type",

            "quantity",

            "requested_price",

            "stop_price",

            "target_price",

            "status",

            "created_at",

        ]

        if c in df.columns

    ]

    st.dataframe(

        df[display_cols],

        use_container_width=True,

        hide_index=True,

    )

    st.divider()

    # ----------------------------------------------------------------------
    # Select Order
    # ----------------------------------------------------------------------

    selected = st.selectbox(

        "Select Order",

        df["broker_order_id"],

    )

    order = next(

        x

        for x in rows

        if x["broker_order_id"] == selected

    )

    st.subheader(
        "Order Details"
    )

    c1, c2 = st.columns(2)

    with c1:

        st.json(order)

    with c2:

        try:

            events = explorer.timeline(

                broker_order_id=selected,

            )

            st.dataframe(

                pd.DataFrame(events),

                use_container_width=True,

                hide_index=True,

            )

        except Exception:

            st.info(
                "No events."
            )

    st.divider()

    # ----------------------------------------------------------------------
    # Modify
    # ----------------------------------------------------------------------

    st.subheader(
        "Modify Pending Order"
    )

    new_qty = st.number_input(

        "Quantity",

        value=float(
            order.get(
                "quantity",
                0,
            )
        ),

    )

    new_limit = st.number_input(

        "Limit",

        value=float(

            order.get(
                "requested_price",
                0,
            )
            or 0

        ),

    )

    new_stop = st.number_input(

        "Stop",

        value=float(

            order.get(
                "stop_price",
                0,
            )
            or 0

        ),

    )

    new_target = st.number_input(

        "Target",

        value=float(

            order.get(
                "target_price",
                0,
            )
            or 0

        ),

    )

    c1, c2, c3 = st.columns(3)

    # ----------------------------------------------------------------------
    # Modify
    # ----------------------------------------------------------------------

    with c1:

        if st.button(

            "Update Order",

            use_container_width=True,

        ):

            context = repo.context_from_order(
                order,
            )

            result = service.modify_order(

                context,

                quantity=new_qty,

                limit_price=new_limit,

                stop_price=new_stop,

                target_price=new_target,

            )

            st.success(
                result.message,
            )

            st.rerun()

    # ----------------------------------------------------------------------
    # Cancel
    # ----------------------------------------------------------------------

    with c2:

        if st.button(

            "Cancel",

            use_container_width=True,

        ):

            context = repo.context_from_order(
                order,
            )

            result = service.cancel_order(
                context,
            )

            st.success(
                result.message,
            )

            st.rerun()

    # ----------------------------------------------------------------------
    # Paper Fill
    # ----------------------------------------------------------------------

    with c3:

        broker = str(

            order.get(
                "broker",
                "",
            )

        ).lower()

        if broker == "paper":

            if st.button(

                "Fill Now",

                use_container_width=True,

            ):

                context = repo.context_from_order(
                    order,
                )

                result = service.fill_pending_order(
                    context,
                )

                st.success(
                    result.message,
                )

                st.rerun()

    st.divider()

    # ----------------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------------

    st.subheader(
        "Pending Order Summary"
    )

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Pending",
        len(rows),
    )

    c2.metric(

        "Buy",

        sum(

            1

            for x in rows

            if x.get("side") == "BUY"

        ),

    )

    c3.metric(

        "Sell",

        sum(

            1

            for x in rows

            if x.get("side") == "SELL"

        ),

    )

    c4.metric(

        "Updated",

        datetime.utcnow().strftime(
            "%H:%M:%S"
        ),

    )

    st.caption(
        "Institutional Forex Pending Orders • FX Sprint 1"
    )