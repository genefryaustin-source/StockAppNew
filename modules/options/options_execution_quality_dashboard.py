"""
Sprint 6 Phase 1 — Execution Quality Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_models import ensure_tables, get_order_history
from modules.options.options_execution_quality_engine import (
    build_execution_quality_report,
    summarize_execution_quality,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_execution_quality_dashboard(
    db,
    tenant_id: str,
    limit: int = 200,
) -> dict[str, Any]:
    st.subheader("⚙️ Execution Quality Intelligence")
    st.caption("Fill quality · Slippage · Midpoint capture · Spread paid · Best execution diagnostics")

    limit = st.slider(
        "Order history sample size",
        min_value=25,
        max_value=1000,
        value=int(limit),
        step=25,
        key="execution_quality_order_limit",
    )

    try:
        ensure_tables(db)
        orders = get_order_history(db, tenant_id, limit=limit)
    except Exception as e:
        st.error(f"Unable to load order history: {e}")
        return {"available": False, "reason": str(e)}

    report = build_execution_quality_report(orders)

    if not report.get("available"):
        st.info(report.get("reason", "No execution data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Execution Grade", summary.get("execution_grade", "—"))
    c2.metric("Avg Score", f"{summary.get('avg_execution_score', 0)}/100")
    c3.metric("Fill Rate", f"{summary.get('fill_rate', 0)}%")
    c4.metric("Filled Orders", f"{summary.get('filled_count', 0)}/{summary.get('order_count', 0)}")

    s1, s2, s3 = st.columns(3)
    s1.metric("Avg Slippage", f"{summary.get('avg_slippage_bps', 0)} bps")
    s2.metric("Avg Spread Paid", f"{summary.get('avg_spread_paid_pct', 0)}%")
    s3.metric("Avg Mid Capture", f"{summary.get('avg_midpoint_capture_pct', 0)}%")

    st.markdown("#### Execution Summary")
    st.info(summarize_execution_quality(report))

    tab_orders, tab_symbol, tab_strategy, tab_mode, tab_broker = st.tabs(
        [
            "Orders",
            "By Symbol",
            "By Strategy",
            "By Mode",
            "By Broker",
        ]
    )

    with tab_orders:
        orders_df = report.get("orders")
        show_cols = [
            "created_at",
            "underlying",
            "option_symbol",
            "side",
            "qty",
            "status",
            "reference_price",
            "execution_price",
            "computed_mid",
            "spread",
            "fill_quality",
            "execution_score",
            "slippage_bps",
            "spread_paid_pct",
            "midpoint_capture_pct",
            "diagnostic",
        ]
        _table(orders_df, show_cols)

    with tab_symbol:
        _table(report.get("by_symbol", {}).get("table"))

    with tab_strategy:
        _table(report.get("by_strategy", {}).get("table"))

    with tab_mode:
        _table(report.get("by_mode", {}).get("table"))

    with tab_broker:
        _table(report.get("by_broker", {}).get("table"))

    return report
