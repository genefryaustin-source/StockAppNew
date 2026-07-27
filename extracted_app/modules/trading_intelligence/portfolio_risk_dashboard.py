from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.portfolio_risk_monitor import (
    PortfolioRiskMonitor,
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


def render_portfolio_risk_dashboard(
    db,
    portfolio_id: str,
):
    st.subheader("🛡️ Portfolio Risk Monitor")
    st.caption(
        "Monitors position concentration, sector exposure, recommendation-linked exposure, "
        "and portfolio-level P&L risk."
    )

    engine = PortfolioRiskMonitor(db)

    c1, c2 = st.columns(2)

    max_position_pct = c1.slider(
        "Max position concentration",
        min_value=5.0,
        max_value=50.0,
        value=15.0,
        step=1.0,
        format="%.0f%%",
    )

    max_sector_pct = c2.slider(
        "Max sector concentration",
        min_value=10.0,
        max_value=75.0,
        value=30.0,
        step=5.0,
        format="%.0f%%",
    )

    try:
        summary = engine.build_summary(portfolio_id)
        positions = engine.load_positions(portfolio_id)
        sectors = engine.sector_exposure(portfolio_id)
        breaches = engine.concentration_breaches(
            portfolio_id=portfolio_id,
            max_position_pct=float(max_position_pct),
            max_sector_pct=float(max_sector_pct),
        )
        rec_exposure = engine.recommendation_exposure(portfolio_id)
    except Exception as e:
        st.error(f"Portfolio risk monitor failed: {e}")
        return

    if summary.position_count == 0:
        st.info("No active positions to monitor.")
        return

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric("Positions", summary.position_count)
    m2.metric("Market Value", _fmt_money(summary.total_market_value))
    m3.metric("Unrealized P&L", _fmt_money(summary.total_unrealized_pnl))
    m4.metric("Largest Position", f"{summary.largest_position_symbol} {summary.largest_position_pct:.1f}%")
    m5.metric("Risk Status", summary.risk_status)

    st.caption(
        f"Concentration: **{summary.concentration_status}** | "
        f"Max sector: **{summary.max_sector} {summary.max_sector_pct:.1f}%**"
    )

    if summary.risk_status == "High Risk":
        st.error("Portfolio risk is elevated. Review concentration and unrealized losses.")
    elif summary.risk_status == "Moderate Risk":
        st.warning("Portfolio risk is moderate. Review sizing and sector exposure.")
    else:
        st.success("Portfolio risk appears controlled.")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs([
        "Positions",
        "Sector Exposure",
        "Breaches",
        "Recommendation Exposure",
    ])

    with tab1:
        st.markdown("### Position Exposure")

        display = positions.copy()

        total_mv = float(display["market_value"].fillna(0).sum()) if not display.empty else 0.0
        display["position_pct"] = display["market_value"].apply(
            lambda v: (float(v or 0) / total_mv * 100.0) if total_mv > 0 else 0.0
        )

        for col in [
            "avg_cost",
            "market_price",
            "market_value",
            "unrealized_pnl",
            "realized_pnl",
        ]:
            if col in display.columns:
                display[col] = display[col].apply(_fmt_money)

        if "position_pct" in display.columns:
            display["position_pct"] = display["position_pct"].apply(_fmt_pct)

        cols = [
            "symbol",
            "qty",
            "avg_cost",
            "market_price",
            "market_value",
            "position_pct",
            "unrealized_pnl",
            "realized_pnl",
            "sector",
            "recommendation",
            "conviction_score",
            "confidence_score",
            "risk_reward",
        ]

        st.dataframe(
            display[[c for c in cols if c in display.columns]],
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        st.markdown("### Sector Exposure")

        if sectors.empty:
            st.info("No sector exposure available.")
        else:
            display = sectors.copy()

            for col in ["market_value", "unrealized_pnl", "realized_pnl"]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            if "sector_pct" in display.columns:
                display["sector_pct"] = display["sector_pct"].apply(_fmt_pct)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

    with tab3:
        st.markdown("### Risk Breaches")

        if breaches.empty:
            st.success("No concentration breaches detected.")
        else:
            for _, row in breaches.iterrows():
                message = (
                    f"{row.get('severity')} | {row.get('breach_type')} | "
                    f"{row.get('symbol_or_sector')} at {row.get('current_pct')}% "
                    f"vs limit {row.get('limit_pct')}%"
                )

                if row.get("severity") == "HIGH":
                    st.error(message)
                else:
                    st.warning(message)

            st.dataframe(
                breaches,
                use_container_width=True,
                hide_index=True,
            )

    with tab4:
        st.markdown("### Recommendation-Linked Exposure")

        if rec_exposure.empty:
            st.info("No recommendation-linked exposure available.")
        else:
            display = rec_exposure.copy()

            for col in ["market_value", "unrealized_pnl"]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    with st.expander("Portfolio Risk Diagnostics", expanded=False):
        st.json(summary.to_dict())