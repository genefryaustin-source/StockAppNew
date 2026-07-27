"""
modules/stocks/stock_execution_intelligence_dashboard.py

Institutional Stock Execution Intelligence Dashboard

Displays:

    - KPI Cards
    - Execution Quality
    - Broker Comparison
    - Transaction Cost Analysis

This is the analytics-intelligence counterpart to
stock_execution_dashboard.py, which covers the operational side (events,
attribution, AI review, compliance). Together they complete the
institutional stock execution analytics stack.

Requires:

    stock_execution_intelligence_dashboard_service.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.stocks.stock_execution_intelligence_dashboard_service import (
    get_stock_execution_intelligence_dashboard_service,
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

        elif fmt == "bps":

            display = f"{value:.2f} bps"

        elif fmt == "score":

            display = f"{value:.1f}"

        elif fmt == "text":

            display = str(value)

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


def _show_cost_breakdown(title, breakdown: dict, value_label: str = "Cost ($)"):

    st.subheader(title)

    if not breakdown:

        st.info("No data available.")

        return

    df = pd.DataFrame(

        [
            {"Key": k, value_label: v}
            for k, v in sorted(breakdown.items(), key=lambda kv: kv[1], reverse=True)
        ]

    )

    st.dataframe(

        df,

        use_container_width=True,

        hide_index=True,
    )


# ==========================================================
# Main Dashboard
# ==========================================================

def render_stock_execution_intelligence_dashboard(

    db,

    *,

    portfolio_id=None,

):

    service = get_stock_execution_intelligence_dashboard_service(
        db,
    )

    dashboard = service.dashboard(

        portfolio_id=portfolio_id,

    )

    st.title(
        "Execution Intelligence"
    )

    st.markdown(
        "Execution Quality · Broker Comparison · Transaction Cost Analysis"
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

            "Execution Quality",

            "Broker Comparison",

            "Transaction Costs",

        ]

    )

    # ======================================================
    # Execution Quality
    # ======================================================

    with tabs[0]:

        summary = dashboard["quality_summary"]

        cols = st.columns(4)

        cols[0].metric(

            "Orders",

            summary.get(
                "order_count",
                0,
            ),
        )

        cols[1].metric(

            "Avg Slippage",

            f"{summary.get('average_slippage_bps', 0):.2f} bps",
        )

        cols[2].metric(

            "Avg Commission",

            f"{summary.get('average_commission_bps', 0):.2f} bps",
        )

        cols[3].metric(

            "Avg Fill Rate",

            f"{summary.get('average_fill_rate', 0):.2f}%",
        )

        st.divider()

        _show_dataframe(

            "Recent Execution Quality Records",

            dashboard["recent_quality_records"],

        )

    # ======================================================
    # Broker Comparison
    # ======================================================

    with tabs[1]:

        broker_summary = dashboard["broker_summary"]

        best_broker = broker_summary.get("best_broker")

        if best_broker:

            st.success(
                f"Best-performing broker: **{best_broker}** "
                f"(quality score {broker_summary.get('best_broker_score', 0):.1f})"
            )

        else:

            st.info("No broker execution history yet.")

        cols = st.columns(2)

        cols[0].metric(

            "Brokers Compared",

            broker_summary.get(
                "broker_count",
                0,
            ),
        )

        cols[1].metric(

            "Best Broker Score",

            f"{broker_summary.get('best_broker_score', 0):.1f}",
        )

        st.divider()

        broker_records = dashboard["broker_records"]

        if not broker_records:

            st.info("No data available.")

        else:

            display_rows = [
                {
                    "Broker": r["broker"],
                    "Orders": r["order_count"],
                    "Rejected": r["rejected_count"],
                    "Rejection Rate": f"{r['rejection_rate']:.2f}%",
                    "Quality Score": r["average_quality_score"],
                    "Grade": r["overall_grade"],
                    "Reliability": r["reliability_rating"],
                    "Avg Slippage (bps)": r["average_slippage_bps"],
                    "Avg Commission (bps)": r["average_commission_bps"],
                    "Avg Latency (ms)": r["average_latency_ms"],
                }
                for r in broker_records
            ]

            st.dataframe(

                pd.DataFrame(display_rows),

                use_container_width=True,

                hide_index=True,
            )

    # ======================================================
    # Transaction Costs
    # ======================================================

    with tabs[2]:

        cost_summary = dashboard["cost_summary"]

        cols = st.columns(4)

        cols[0].metric(

            "Total Notional",

            f"${cost_summary.get('total_notional', 0):,.2f}",
        )

        cols[1].metric(

            "Total Cost",

            f"${cost_summary.get('total_cost', 0):,.2f}",
        )

        cols[2].metric(

            "Blended Cost",

            f"{cost_summary.get('blended_total_cost_bps', 0):.2f} bps",
        )

        cost_pct = cost_summary.get("cost_as_pct_of_equity")

        cols[3].metric(

            "Cost % of Equity",

            f"{cost_pct:.4f}%" if cost_pct is not None else "N/A",
        )

        st.divider()

        cost_detail = dashboard["cost_detail"]

        col_a, col_b = st.columns(2)

        with col_a:

            _show_cost_breakdown(
                "Cost by Symbol",
                cost_detail.get("cost_by_symbol", {}),
            )

        with col_b:

            _show_cost_breakdown(
                "Cost by Side",
                cost_detail.get("cost_by_side", {}),
            )

        st.divider()

        st.subheader("Cost by Trade Size")

        size_buckets = cost_detail.get("cost_by_size_bucket", {})

        if size_buckets:

            bucket_rows = [
                {
                    "Bucket": name,
                    "Orders": stats.get("order_count", 0),
                    "Total Cost ($)": stats.get("total_cost", 0),
                    "Avg Cost (bps)": stats.get("average_cost_bps", 0),
                }
                for name, stats in size_buckets.items()
            ]

            st.dataframe(

                pd.DataFrame(bucket_rows),

                use_container_width=True,

                hide_index=True,
            )

        else:

            st.info("No data available.")

        st.divider()

        st.subheader("Cost Trend")

        trend = dashboard["cost_trend"]

        if trend:

            trend_df = pd.DataFrame(trend).set_index("period")

            st.line_chart(

                trend_df[["blended_cost_bps"]],

                use_container_width=True,
            )

            st.dataframe(

                trend_df,

                use_container_width=True,
            )

        else:

            st.info("No data available.")