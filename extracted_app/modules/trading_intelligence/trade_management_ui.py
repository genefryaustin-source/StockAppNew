"""
modules/trading_intelligence/trade_management_ui.py

Trade Command Center

Provides:

    • Open Trade Monitoring
    • Stop Loss Alerts
    • Target Hit Alerts
    • Trailing Profit Opportunities
    • Trade Health Dashboard
    • Recommendation Attribution
    • Position Risk Monitoring
    • Trade Lifecycle Analytics

Dependencies:

    modules.trading_intelligence.trade_management_engine
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.trade_management_engine import (
    TradeManagementEngine,
)


# ============================================================
# HELPERS
# ============================================================

STATUS_EMOJI = {
    "STOP_ALERT": "🛑",
    "TARGET_HIT": "🎯",
    "TRAILING_PROFIT": "📈",
    "CAUTION": "⚠️",
    "OPEN": "✅",
}


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


def _render_summary(metrics: dict):

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric(
        "Open Trades",
        metrics.get("open_positions", 0),
    )

    c2.metric(
        "Target Hits",
        metrics.get("target_hits", 0),
    )

    c3.metric(
        "Stop Alerts",
        metrics.get("stop_alerts", 0),
    )

    c4.metric(
        "Cautions",
        metrics.get("cautions", 0),
    )

    c5.metric(
        "Trailing Profit",
        metrics.get("trailing_profit", 0),
    )


def _render_alert_banner(df: pd.DataFrame):

    if df.empty:
        return

    stop_count = len(
        df[df["status"] == "STOP_ALERT"]
    )

    target_count = len(
        df[df["status"] == "TARGET_HIT"]
    )

    caution_count = len(
        df[df["status"] == "CAUTION"]
    )

    if stop_count > 0:
        st.error(
            f"🚨 {stop_count} position(s) have breached stop levels."
        )

    if target_count > 0:
        st.success(
            f"🎯 {target_count} position(s) reached target."
        )

    if caution_count > 0:
        st.warning(
            f"⚠️ {caution_count} position(s) require review."
        )


# ============================================================
# MAIN UI
# ============================================================

def render_trade_management_ui(
    db,
    portfolio_id: str,
):

    st.subheader("🎯 Trade Command Center")

    engine = TradeManagementEngine(db)

    try:

        metrics = engine.get_summary_metrics(
            portfolio_id
        )

        df = engine.get_trade_management_dataframe(
            portfolio_id
        )

    except Exception as e:

        st.error(
            f"Trade management engine failed: {e}"
        )
        return

    if df.empty:

        st.info(
            "No active positions available."
        )
        return

    _render_summary(metrics)

    st.divider()

    _render_alert_banner(df)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Open Trades",
        "Alerts",
        "Risk Monitor",
        "Recommendation Attribution",
    ])

    # ========================================================
    # OPEN TRADES
    # ========================================================

    with tab1:

        st.markdown(
            "### Active Trade Monitoring"
        )

        display = df.copy()

        display["Status"] = display["status"].map(
            lambda x: f"{STATUS_EMOJI.get(x,'')} {x}"
        )

        display["Entry"] = display[
            "entry_price"
        ].apply(_fmt_money)

        display["Current"] = display[
            "current_price"
        ].apply(_fmt_money)

        display["Unrealized PnL"] = display[
            "unrealized_pnl"
        ].apply(_fmt_money)

        display["PnL %"] = display[
            "unrealized_pnl_pct"
        ].apply(_fmt_pct)

        cols = [
            "Status",
            "symbol",
            "recommendation",
            "conviction_score",
            "confidence_score",
            "Entry",
            "Current",
            "Unrealized PnL",
            "PnL %",
            "days_held",
            "message",
        ]

        st.dataframe(
            display[cols],
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # ALERTS
    # ========================================================

    with tab2:

        st.markdown(
            "### Trade Alerts"
        )

        alerts = df[
            df["status"].isin(
                [
                    "STOP_ALERT",
                    "TARGET_HIT",
                    "TRAILING_PROFIT",
                    "CAUTION",
                ]
            )
        ].copy()

        if alerts.empty:

            st.success(
                "No active alerts."
            )

        else:

            for _, row in alerts.iterrows():

                status = row["status"]

                msg = (
                    f"{row['symbol']} | "
                    f"{row['message']}"
                )

                if status == "STOP_ALERT":
                    st.error(msg)

                elif status == "TARGET_HIT":
                    st.success(msg)

                elif status == "TRAILING_PROFIT":
                    st.info(msg)

                else:
                    st.warning(msg)

    # ========================================================
    # RISK MONITOR
    # ========================================================

    with tab3:

        st.markdown(
            "### Risk & Reward Monitor"
        )

        risk_view = df.copy()

        risk_view["Current"] = risk_view[
            "current_price"
        ].apply(_fmt_money)

        risk_view["Stop"] = risk_view[
            "stop_price"
        ].apply(_fmt_money)

        risk_view["Target"] = risk_view[
            "target_price"
        ].apply(_fmt_money)

        risk_view["Current RR"] = risk_view[
            "risk_reward_current"
        ]

        risk_cols = [
            "symbol",
            "Current",
            "Stop",
            "Target",
            "Current RR",
            "status",
        ]

        st.dataframe(
            risk_view[risk_cols],
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # ATTRIBUTION
    # ========================================================

    with tab4:

        st.markdown(
            "### Recommendation Attribution"
        )

        attribution = df.copy()

        attribution["PnL %"] = attribution[
            "unrealized_pnl_pct"
        ].apply(_fmt_pct)

        attribution = attribution[[
            "symbol",
            "recommendation",
            "conviction_score",
            "confidence_score",
            "days_held",
            "PnL %",
        ]]

        st.dataframe(
            attribution,
            use_container_width=True,
            hide_index=True,
        )

        st.divider()

        st.markdown(
            "#### Recommendation Distribution"
        )

        dist = (
            df["recommendation"]
            .value_counts()
            .reset_index()
        )

        dist.columns = [
            "Recommendation",
            "Count",
        ]

        st.dataframe(
            dist,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    with st.expander(
        "Trade Management Engine Diagnostics",
        expanded=False,
    ):

        st.write(
            {
                "positions_loaded": len(df),
                "stop_alerts":
                    metrics.get(
                        "stop_alerts",
                        0,
                    ),
                "target_hits":
                    metrics.get(
                        "target_hits",
                        0,
                    ),
                "cautions":
                    metrics.get(
                        "cautions",
                        0,
                    ),
                "trailing_profit":
                    metrics.get(
                        "trailing_profit",
                        0,
                    ),
            }
        )