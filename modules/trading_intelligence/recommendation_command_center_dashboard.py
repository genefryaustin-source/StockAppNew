from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.recommendation_command_center import (
    RecommendationCommandCenter,
)


def _fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "$0.00"


def _fmt_pct(v):
    try:
        return f"{float(v):,.2f}%"
    except Exception:
        return "0.00%"


def render_recommendation_command_center_dashboard(
    db,
    portfolio_id=None,
):
    st.subheader("🧠 Recommendation Command Center")
    st.caption(
        "Unified control tower for recommendation lifecycle, alerts, targets, stops, attribution, performance, and portfolio risk."
    )

    center = RecommendationCommandCenter(db)

    c1, c2 = st.columns([1, 1])

    persist_alerts = c1.checkbox(
        "Persist active alerts",
        value=False,
        key="command_center_persist_alerts",
    )

    if c2.button(
        "Refresh Command Center",
        key="refresh_recommendation_command_center",
    ):
        st.rerun()

    try:
        snapshot = center.build_command_snapshot(
            portfolio_id=portfolio_id,
            persist_alerts=persist_alerts,
        )
        health = center.build_health_score(
            portfolio_id=portfolio_id,
        )
        views = center.load_all_views(
            portfolio_id=portfolio_id,
        )
    except Exception as e:
        st.error(f"Recommendation Command Center failed: {e}")
        return

    st.divider()

    h1, h2, h3, h4 = st.columns(4)

    h1.metric("Health Score", health.get("score", 0))
    h2.metric("Health Status", health.get("status", "Unknown"))
    h3.metric("Active Alerts", snapshot.get("active_alerts", 0))
    h4.metric(
        "Execution Rate",
        _fmt_pct(
            snapshot
            .get("lifecycle_metrics", {})
            .get("execution_rate", 0)
        ),
    )

    reasons = health.get("reasons", [])
    if reasons:
        st.warning(" | ".join(reasons))
    else:
        st.success("Recommendation command center is operating normally.")

    st.divider()

    a1, a2, a3, a4, a5 = st.columns(5)

    alert_counts = snapshot.get("alert_counts", {})

    a1.metric("Critical", alert_counts.get("critical", 0))
    a2.metric("High", alert_counts.get("high", 0))
    a3.metric("Medium", alert_counts.get("medium", 0))
    a4.metric("Low", alert_counts.get("low", 0))
    a5.metric("Info", alert_counts.get("info", 0))

    st.divider()

    t1, t2, t3, t4, t5 = st.columns(5)

    lifecycle_metrics = snapshot.get("lifecycle_metrics", {})
    target_summary = snapshot.get("target_summary", {})
    stop_summary = snapshot.get("stop_summary", {})
    risk_summary = snapshot.get("risk_summary", {})
    perf_summary = snapshot.get("performance_summary", {})

    t1.metric("Recommendations", lifecycle_metrics.get("total", 0))
    t2.metric("Executed", lifecycle_metrics.get("executed", 0))
    t3.metric("Target Hits", target_summary.get("target_hits", 0))
    t4.metric("Stop Breaches", stop_summary.get("stop_breaches", 0))
    t5.metric("Risk Status", risk_summary.get("risk_status", "—"))

    p1, p2, p3, p4 = st.columns(4)

    p1.metric(
        "Win Rate",
        _fmt_pct(perf_summary.get("win_rate", 0)),
    )
    p2.metric(
        "Total P&L",
        _fmt_money(perf_summary.get("total_net_pnl", 0)),
    )
    p3.metric(
        "Open Positions",
        risk_summary.get("position_count", 0),
    )
    p4.metric(
        "Market Value",
        _fmt_money(risk_summary.get("total_market_value", 0)),
    )

    st.divider()

    tabs = st.tabs([
        "Alerts",
        "Lifecycle",
        "Targets",
        "Stops",
        "Trade Management",
        "Attribution",
        "Risk",
        "Diagnostics",
    ])

    with tabs[0]:
        st.markdown("### Active Recommendation Alerts")

        alerts = views.get("alerts", pd.DataFrame())

        if alerts.empty:
            st.success("No active alerts.")
        else:
            st.dataframe(
                alerts,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[1]:
        st.markdown("### Recommendation Lifecycle")

        lifecycle = views.get("lifecycle", pd.DataFrame())

        if lifecycle.empty:
            st.info("No lifecycle data.")
        else:
            st.dataframe(
                lifecycle,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[2]:
        st.markdown("### Target Tracking")

        targets = views.get("targets", pd.DataFrame())

        if targets.empty:
            st.info("No active target tracking data.")
        else:
            st.dataframe(
                targets,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[3]:
        st.markdown("### Stop-Loss Monitor")

        stops = views.get("stops", pd.DataFrame())

        if stops.empty:
            st.info("No stop-loss monitoring data.")
        else:
            st.dataframe(
                stops,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[4]:
        st.markdown("### Trade Management")

        trade_mgmt = views.get("trade_management", pd.DataFrame())

        if trade_mgmt.empty:
            st.info("No active trade management data.")
        else:
            st.dataframe(
                trade_mgmt,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[5]:
        st.markdown("### Recommendation Attribution")

        attribution = views.get("attribution", pd.DataFrame())

        if attribution.empty:
            st.info("No attribution data.")
        else:
            st.dataframe(
                attribution,
                use_container_width=True,
                hide_index=True,
            )

    with tabs[6]:
        st.markdown("### Portfolio Risk")

        risk_positions = views.get("risk_positions", pd.DataFrame())
        sector_risk = views.get("sector_risk", pd.DataFrame())

        rtab1, rtab2 = st.tabs([
            "Positions",
            "Sector Exposure",
        ])

        with rtab1:
            if risk_positions.empty:
                st.info("No active risk positions.")
            else:
                st.dataframe(
                    risk_positions,
                    use_container_width=True,
                    hide_index=True,
                )

        with rtab2:
            if sector_risk.empty:
                st.info("No sector risk data.")
            else:
                st.dataframe(
                    sector_risk,
                    use_container_width=True,
                    hide_index=True,
                )

    with tabs[7]:
        st.markdown("### Command Center Snapshot")

        st.json(snapshot)

        st.markdown("### Self-Test")

        test = center.self_test(
            portfolio_id=portfolio_id,
        )

        if test.get("success"):
            st.success("Command Center validation passed.")
            st.json(test)
        else:
            st.error(test.get("error", "Unknown error"))