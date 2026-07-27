from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.trading_intelligence.trade_attribution_engine import (
    TradeAttributionEngine,
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


def render_trade_attribution_ui(
    db,
    portfolio_id: str,
):
    st.subheader("🧭 Trade Attribution Analytics")
    st.caption(
        "Connects AI recommendations to executed orders, fills, closed trades, "
        "signals, sectors, conviction bands, and realized outcomes."
    )

    engine = TradeAttributionEngine(db)

    try:
        summary = engine.build_summary(portfolio_id)
        attribution = engine.load_attribution_table(portfolio_id)
        signal_df = engine.signal_attribution(portfolio_id)
        sector_df = engine.sector_attribution(portfolio_id)
        conviction_df = engine.conviction_band_attribution(portfolio_id)
        exposure_df = engine.open_recommendation_exposure(portfolio_id)
    except Exception as e:
        st.error(f"Trade attribution failed: {e}")
        return

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric("Linked Trades", summary.linked_trades)
    m2.metric("Closed Linked Trades", summary.closed_linked_trades)
    m3.metric("Win Rate", _fmt_pct(summary.win_rate))
    m4.metric("Total Net P&L", _fmt_money(summary.total_net_pnl))
    m5.metric("Avg Net P&L", _fmt_money(summary.avg_net_pnl))

    st.caption(
        f"Best signal: **{summary.best_signal}** | "
        f"Best sector: **{summary.best_sector}**"
    )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Trade Linkage",
        "Signal Attribution",
        "Sector Attribution",
        "Conviction Bands",
        "Open Exposure",
    ])

    with tab1:
        st.markdown("### Recommendation → Trade Linkage")

        if attribution.empty:
            st.info("No attribution records found.")
        else:
            display = attribution.copy()

            money_cols = [
                "recommended_entry",
                "recommended_stop",
                "recommended_target",
                "avg_fill_price",
                "actual_entry",
                "actual_exit",
                "gross_pnl",
                "net_pnl",
            ]

            for col in money_cols:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            if "return_pct" in display.columns:
                display["return_pct"] = display["return_pct"].apply(_fmt_pct)

            cols = [
                "recommended_at",
                "symbol",
                "recommendation",
                "conviction_score",
                "confidence_score",
                "risk_reward",
                "signal",
                "sector",
                "executed",
                "order_id",
                "order_status",
                "avg_fill_price",
                "outcome",
                "net_pnl",
                "return_pct",
            ]

            st.dataframe(
                display[[c for c in cols if c in display.columns]],
                use_container_width=True,
                hide_index=True,
            )

    with tab2:
        st.markdown("### Signal Attribution")

        if signal_df.empty:
            st.info("No closed trades available for signal attribution yet.")
        else:
            display = signal_df.copy()

            for col in ["total_net_pnl", "avg_net_pnl"]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            if "avg_return_pct" in display.columns:
                display["avg_return_pct"] = display["avg_return_pct"].apply(_fmt_pct)

            if "win_rate" in display.columns:
                display["win_rate"] = display["win_rate"].apply(_fmt_pct)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

    with tab3:
        st.markdown("### Sector Attribution")

        if sector_df.empty:
            st.info("No closed trades available for sector attribution yet.")
        else:
            display = sector_df.copy()

            for col in ["total_net_pnl", "avg_net_pnl"]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            if "avg_return_pct" in display.columns:
                display["avg_return_pct"] = display["avg_return_pct"].apply(_fmt_pct)

            if "win_rate" in display.columns:
                display["win_rate"] = display["win_rate"].apply(_fmt_pct)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

    with tab4:
        st.markdown("### Conviction Band Attribution")

        if conviction_df.empty:
            st.info("No closed trades available for conviction attribution yet.")
        else:
            display = conviction_df.copy()

            for col in ["total_net_pnl", "avg_net_pnl"]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            if "avg_return_pct" in display.columns:
                display["avg_return_pct"] = display["avg_return_pct"].apply(_fmt_pct)

            if "win_rate" in display.columns:
                display["win_rate"] = display["win_rate"].apply(_fmt_pct)

            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
            )

    with tab5:
        st.markdown("### Open Recommendation Exposure")

        if exposure_df.empty:
            st.info("No executed recommendation exposure found.")
        else:
            display = exposure_df.copy()

            for col in [
                "avg_cost",
                "market_price",
                "market_value",
                "unrealized_pnl",
                "realized_pnl",
            ]:
                if col in display.columns:
                    display[col] = display[col].apply(_fmt_money)

            cols = [
                "symbol",
                "recommendation",
                "conviction_score",
                "confidence_score",
                "risk_reward",
                "signal",
                "sector",
                "qty",
                "avg_cost",
                "market_price",
                "market_value",
                "unrealized_pnl",
                "realized_pnl",
            ]

            st.dataframe(
                display[[c for c in cols if c in display.columns]],
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    with st.expander("Attribution Diagnostics", expanded=False):
        st.json(summary.to_dict())