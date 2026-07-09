"""
modules/execution/execution_metrics_dashboard.py

Sprint 40.5

Institutional Execution Metrics Dashboard

Execution analytics workstation built on immutable execution events.

This dashboard delegates all calculations to the
ExecutionEventMetrics engine.

Designed for Streamlit.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go

    PLOTLY = True
except Exception:
    PLOTLY = False

from modules.execution.execution_event_metrics import (
    get_execution_event_metrics,
)

from modules.execution.execution_event_explorer import (
    get_execution_event_explorer,
)

from modules.execution.execution_audit_engine import (
    get_execution_audit_engine,
)

from modules.execution.execution_compliance_engine import (
    get_execution_compliance_engine,
)


# ==============================================================================
# Helpers
# ==============================================================================


def metric_card(title, value):

    st.metric(
        label=title,
        value=value,
    )


# ==============================================================================
# Dashboard
# ==============================================================================


def render_execution_metrics_dashboard(
    db,
    portfolio_engine=None,
):

    st.title("📊 Institutional Execution Metrics Dashboard")

    metrics = get_execution_event_metrics(
        db=db,
    )

    explorer = get_execution_event_explorer(
        db=db,
    )

    audit = get_execution_audit_engine(
        db=db,
    )

    compliance = get_execution_compliance_engine(
        db=db,
    )

    if st.button(
        "Refresh Metrics",
        use_container_width=True,
    ):
        st.rerun()

    aggregate = metrics.aggregate_metrics()

    execution = aggregate.get(
        "execution_metrics",
        {},
    )

    orders = aggregate.get(
        "order_metrics",
        {},
    )

    positions = aggregate.get(
        "position_metrics",
        {},
    )

    latency = aggregate.get(
        "latency_metrics",
        {},
    )

    throughput = aggregate.get(
        "throughput_metrics",
        {},
    )

    quality = aggregate.get(
        "quality_metrics",
        {},
    )

    accounts = aggregate.get(
        "account_metrics",
        {},
    )

    portfolios = aggregate.get(
        "portfolio_metrics",
        {},
    )

    # ======================================================================
    # KPI Cards
    # ======================================================================

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        metric_card(
            "Executions",
            execution.get(
                "total_executions",
                0,
            ),
        )

        metric_card(
            "Orders",
            orders.get(
                "orders",
                0,
            ),
        )

    with c2:

        metric_card(
            "Positions",
            positions.get(
                "opened",
                0,
            ),
        )

        metric_card(
            "Fill Rate",
            f"{orders.get('fill_rate',0):.2%}",
        )

    with c3:

        metric_card(
            "Avg Fill",
            f"{latency.get('average',0):.2f}s",
        )

        metric_card(
            "Latency P95",
            f"{latency.get('p95',0):.2f}s",
        )

    with c4:

        metric_card(
            "Avg Slippage",
            quality.get(
                "average_slippage",
                0,
            ),
        )

        metric_card(
            "Avg Commission",
            quality.get(
                "average_commission",
                0,
            ),
        )

    st.divider()

    # ======================================================================
    # Workspace
    # ======================================================================

    workspace = st.radio(

        "Workspace",

        [

            "Overview",

            "Execution",

            "Orders",

            "Positions",

            "Latency",

            "Throughput",

            "Quality",

            "Accounts",

            "Portfolios",

            "Trends",

            "Export",

        ],

        horizontal=True,

    )

    # ======================================================================
    # Overview
    # ======================================================================

    if workspace == "Overview":

        st.subheader(
            "Aggregate Metrics"
        )

        rows = []

        for section, values in aggregate.items():

            if isinstance(values, dict):

                for k, v in values.items():

                    rows.append({

                        "Section": section,

                        "Metric": k,

                        "Value": v,

                    })

        st.dataframe(

            pd.DataFrame(rows),

            use_container_width=True,

            hide_index=True,

        )

        with st.expander(
            "Raw JSON"
        ):

            st.json(
                aggregate,
            )

    # ======================================================================
    # Execution
    # ======================================================================

    elif workspace == "Execution":

        st.subheader(
            "Execution Metrics"
        )

        st.json(
            execution,
        )

    # ======================================================================
    # Orders
    # ======================================================================

    elif workspace == "Orders":

        st.subheader(
            "Order Metrics"
        )

        st.json(
            orders,
        )

    # ======================================================================
    # Positions
    # ======================================================================

    elif workspace == "Positions":

        st.subheader(
            "Position Metrics"
        )

        st.json(
            positions,
        )

    # ======================================================================
    # Latency
    # ======================================================================

    elif workspace == "Latency":

        st.subheader(
            "Latency"
        )

        st.json(
            latency,
        )

        values = []

        try:

            events = explorer.search()

            for event in events:

                if event.get(
                    "latency"
                ) is not None:

                    values.append(

                        float(
                            event[
                                "latency"
                            ]
                        )

                    )

        except Exception:

            pass

        if values:

            if PLOTLY:

                fig = go.Figure()

                fig.add_histogram(
                    x=values,
                )

                fig.update_layout(

                    title="Latency Distribution",

                    xaxis_title="Seconds",

                    yaxis_title="Frequency",

                )

                st.plotly_chart(

                    fig,

                    use_container_width=True,

                )

            else:

                st.bar_chart(
                    values,
                )

    # ======================================================================
    # Throughput
    # ======================================================================

    elif workspace == "Throughput":

        st.subheader(
            "Throughput"
        )

        st.json(
            throughput,
        )

    # ======================================================================
    # Quality
    # ======================================================================

    elif workspace == "Quality":

        st.subheader(
            "Execution Quality"
        )

        st.json(
            quality,
        )

    # ======================================================================
    # Accounts
    # ======================================================================

    elif workspace == "Accounts":

        st.subheader(
            "Account Metrics"
        )

        st.json(
            accounts,
        )

    # ======================================================================
    # Portfolios
    # ======================================================================

    elif workspace == "Portfolios":

        st.subheader(
            "Portfolio Metrics"
        )

        st.json(
            portfolios,
        )

    # ======================================================================
    # Trends
    # ======================================================================

    elif workspace == "Trends":

        st.subheader(
            "Daily Trends"
        )

        events = explorer.search()

        daily = {}

        for event in events:

            ts = (
                event.get(
                    "occurred_at"
                )
                or event.get(
                    "created_at"
                )
            )

            if ts is None:
                continue

            if isinstance(
                ts,
                str,
            ):

                try:

                    ts = datetime.fromisoformat(
                        ts,
                    )

                except Exception:

                    continue

            key = ts.date()

            daily.setdefault(
                key,
                0,
            )

            daily[key] += 1

        if daily:

            df = pd.DataFrame({

                "Date": list(
                    daily.keys()
                ),

                "Events": list(
                    daily.values()
                ),

            })

            st.line_chart(

                df.set_index(
                    "Date"
                ),

            )

            st.dataframe(

                df,

                use_container_width=True,

                hide_index=True,

            )

        else:

            st.info(
                "No historical events."
            )

    # ======================================================================
    # Export
    # ======================================================================

    elif workspace == "Export":

        export = st.selectbox(

            "Export",

            [

                "Aggregate JSON",

                "Execution JSON",

                "Orders JSON",

                "Positions JSON",

                "Latency JSON",

                "CSV",

            ],

        )

        payload = ""

        filename = "metrics.json"

        if export == "Aggregate JSON":

            payload = json.dumps(

                aggregate,

                indent=4,

                default=str,

            )

        elif export == "Execution JSON":

            payload = json.dumps(

                execution,

                indent=4,

                default=str,

            )

        elif export == "Orders JSON":

            payload = json.dumps(

                orders,

                indent=4,

                default=str,

            )

        elif export == "Positions JSON":

            payload = json.dumps(

                positions,

                indent=4,

                default=str,

            )

        elif export == "Latency JSON":

            payload = json.dumps(

                latency,

                indent=4,

                default=str,

            )

        else:

            payload = explorer.export_csv()

            filename = "execution_events.csv"

        st.download_button(

            "Download",

            payload,

            file_name=filename,

            mime="application/json",

        )

    st.divider()

    st.caption(
        "Institutional Execution Metrics Dashboard • Sprint 40.5"
    )