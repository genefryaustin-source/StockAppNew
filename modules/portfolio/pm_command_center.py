from __future__ import annotations

import pandas as pd
import streamlit as st


def render_pm_command_center(
    portfolio_id,
    totals,
    health,
    drift_df,
    sleeve_df,
    optimized_df,
    alerts,
    monitoring_service,
    rebalance_df,
):

    st.title("📊 PM Command Center")

    # ---------------------------------
    # Top Metrics
    # ---------------------------------
    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Equity", f"${totals.get('equity', 0):,.0f}")
    c2.metric("Net P&L", f"${totals.get('net_pnl', 0):,.0f}")
    c3.metric("Health Score", f"{health.get('score', 0):.1f}")
    c4.metric("Regime", health.get("regime", "Unknown"))

    # ---------------------------------
    # Alerts
    # ---------------------------------
    st.subheader("⚠️ Active Alerts")

    if alerts:
        for a in alerts[:10]:
            st.warning(f"{a['title']} | {a['message']}")
    else:
        st.success("No active alerts")

    # ---------------------------------
    # Strategy Health
    # ---------------------------------
    st.subheader("🧠 Strategy Health")

    if sleeve_df is not None and not sleeve_df.empty:
        st.dataframe(sleeve_df, use_container_width=True)
    else:
        st.caption("No sleeve data")

    # ---------------------------------
    # Drift Monitor
    # ---------------------------------
    st.subheader("📉 Drift Monitor")

    if drift_df is not None and not drift_df.empty:
        st.dataframe(drift_df, use_container_width=True)
    else:
        st.caption("No drift data")

    # ---------------------------------
    # Optimizer Output
    # ---------------------------------
    st.subheader("⚙️ Optimized Allocation")

    if optimized_df is not None and not optimized_df.empty:
        st.dataframe(optimized_df, use_container_width=True)
    else:
        st.caption("No optimizer output")

    # ---------------------------------
    # Execution Readiness
    # ---------------------------------
    st.subheader("🚀 Execution Readiness")

    if rebalance_df is not None and not rebalance_df.empty:
        st.success(f"{len(rebalance_df)} trades ready")

        if st.button("Execute Rebalance (PM Panel)"):
            st.warning("Use execution panel below (controlled path)")
    else:
        st.caption("No trades ready")

    # ---------------------------------
    # System Health
    # ---------------------------------
    st.subheader("🤖 System Status")

    s1, s2, s3 = st.columns(3)

    s1.metric("Scheduler Running", "Yes" if monitoring_service else "Unknown")
    s2.metric("Last Status", getattr(monitoring_service, "last_cycle_status", "N/A"))
    s3.metric("Heartbeat", getattr(monitoring_service, "last_heartbeat", "N/A"))

    # ---------------------------------
    # Audit Feed
    # ---------------------------------
    st.subheader("📜 Audit Feed")

    audit_df = monitoring_service.audit_df() if monitoring_service else pd.DataFrame()

    if not audit_df.empty:
        st.dataframe(audit_df.tail(20), use_container_width=True)
    else:
        st.caption("No audit events")