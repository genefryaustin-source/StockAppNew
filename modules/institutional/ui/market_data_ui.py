import math

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text
from modules.analytics.incremental_runner import run_incremental_analytics
from modules.market_data.service import (
    clear_price_cache,
    get_price_history,
    get_price_history_page_from_db,
    get_stale_symbols,
)
from modules.market_data.updater import update_latest_prices
from modules.market_data.models import PriceHistory

# ---------------------------------------------------
# INDICATORS
# ---------------------------------------------------

def _add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if out.empty:
        return out

    out["Date"] = pd.to_datetime(out["Date"])
    out = out.sort_values("Date").reset_index(drop=True)

    if len(out) >= 50:
        out["SMA50"] = out["Close"].rolling(50).mean()

    if len(out) >= 200:
        out["SMA200"] = out["Close"].rolling(200).mean()

    if len(out) >= 14:
        delta = out["Close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = -delta.clip(upper=0).rolling(14).mean()
        rs = gain / loss
        out["RSI14"] = 100 - (100 / (1 + rs))

    return out


# ---------------------------------------------------
# CHART
# ---------------------------------------------------

def _render_chart(df: pd.DataFrame, symbol: str):
    if df.empty:
        st.warning("No chart data found.")
        return

    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=symbol,
        )
    )

    if "SMA50" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA50"], name="SMA50"))

    if "SMA200" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA200"], name="SMA200"))

    fig.update_layout(
        title=f"{symbol} Price History",
        height=550,
        xaxis_title="Date",
        yaxis_title="Price",
    )

    st.plotly_chart(fig, use_container_width=True)

    if "RSI14" in df.columns:
        st.subheader("RSI (14)")
        rsi_df = df[["Date", "RSI14"]].dropna().set_index("Date")
        if not rsi_df.empty:
            st.line_chart(rsi_df)


# ---------------------------------------------------
# VIEWER
# ---------------------------------------------------

def render_market_data(db, user):
    st.subheader("Market Data")

    c1, c2, c3, c4 = st.columns([2, 1, 1, 1])

    with c1:
        symbol = st.text_input("Symbol", "PLTR").upper().strip()

    with c2:
        period = st.selectbox("Period", ["3mo", "6mo", "1y", "2y", "5y"], index=2)

    with c3:
        page_size = st.selectbox("Rows per page", [100, 250, 500, 1000], index=1)

    with c4:
        force_refresh = st.checkbox("Force API Refresh", value=False)

    load = st.button("Load Data", type="primary")

    if load:
        # Full chart dataset
        chart_df = get_price_history(
            db,
            symbol,
            period=period,
            interval="1d",
            force_refresh=force_refresh,
        )
        st.write("DEBUG CHART_DF TYPE:", type(chart_df))

        if chart_df is not None:
            st.write("DEBUG ROWS:", len(chart_df))
            st.write("DEBUG COLUMNS:", list(chart_df.columns))

            if not chart_df.empty:
                st.dataframe(chart_df.head())
        st.write(
            "Chart Rows:",
            len(chart_df)
        )

        st.dataframe(
            chart_df.head()
        )
        if chart_df is None or chart_df.empty:
            st.warning("No market data returned.")
            return

        chart_df = _add_indicators(chart_df)
        _render_chart(chart_df, symbol)

        st.subheader("Price History Table")

        total_rows = len(chart_df)
        total_pages = max(1, math.ceil(total_rows / page_size))

        page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
        )

        # Use DB-backed page when not forcing API refresh
        if not force_refresh:
            page_df, db_total = get_price_history_page_from_db(
                db,
                symbol,
                period=period,
                page=int(page),
                page_size=int(page_size),
            )

            if db_total > 0 and not page_df.empty:
                st.caption(f"DB-backed rows: {db_total}")
                st.dataframe(page_df, use_container_width=True, height=600)
            else:
                start = (int(page) - 1) * int(page_size)
                end = start + int(page_size)
                st.caption(f"Rows returned: {len(chart_df)}")
                st.dataframe(chart_df.iloc[start:end], use_container_width=True, height=600)
        else:
            start = (int(page) - 1) * int(page_size)
            end = start + int(page_size)
            st.caption(f"Rows returned: {len(chart_df)}")
            st.dataframe(chart_df.iloc[start:end], use_container_width=True, height=600)

    try:

        st.write("DEBUG: Checking PriceHistory")

        rows = db.query(
            PriceHistory
        ).count()

        st.write(
            "PriceHistory rows:",
            rows
        )

    except Exception as e:

        st.exception(e)
    st.divider()

    st.subheader("Data Freshness")

    try:
        stale_df = get_stale_symbols(db, limit=20)

        if stale_df.empty:
            st.info("No freshness data available.")
        else:
            st.dataframe(stale_df, use_container_width=True)
    except Exception as e:
        st.warning(f"Freshness check failed: {e}")


# ---------------------------------------------------
# REFRESH + AUTO ANALYTICS
# ---------------------------------------------------

def render_market_refresh(db, user):
    st.subheader("🔄 Market Data Refresh")

    c1, c2 = st.columns(2)

    with c1:
        limit = st.number_input(
            "Limit symbols (0 = all)",
            min_value=0,
            value=0,
            step=100,
        )

    with c2:
        run = st.button("Refresh Latest Prices", type="primary")

    clear = st.button("Clear Market Data Cache")

    if clear:
        try:
            clear_price_cache()
            st.success("Market data cache cleared.")
        except Exception as e:
            st.error(f"Failed to clear cache: {e}")

    if run:
        try:
            query = (text("""SELECT symbol FROM universe_equities"""))
            if limit > 0:
                query += f" LIMIT {int(limit)}"

            rows = db.execute(query).fetchall()
            symbols = [r[0] for r in rows]

            if not symbols:
                st.warning("No symbols found.")
                return

            st.info(f"Refreshing {len(symbols)} symbols...")

            progress_bar = st.progress(0)
            status = st.empty()

            def progress_callback(i, total, sym):
                pct = int((i / total) * 100)
                progress_bar.progress(pct)
                status.text(f"{i}/{total} - {sym}")

            result = update_latest_prices(
                db,
                symbols,
                progress_callback=progress_callback,
            )

            updated_symbols = result.get("updated_symbols", [])

            st.success(
                f"""
✅ Market Data Refresh Complete

Total: {result['total']}
Updated: {result['updated']}
Skipped: {result['skipped']}
Failed: {result['failed']}
"""
            )

            if updated_symbols:
                st.info(f"Running analytics for {len(updated_symbols)} updated symbols...")

                analytics_result = run_incremental_analytics(
                    db,
                    user["tenant_id"],
                    updated_symbols,
                )

                st.success(
                    f"""

from modules.analytics.runner import enrich_missing_fundamentals

enriched = enrich_missing_fundamentals(
    db,
    user["tenant_id"],
    updated_symbols,
    limit=200,
)

st.info(f"Fundamentals enriched: {enriched}")


📊 Analytics Updated

Processed: {analytics_result['processed']}
Failed: {analytics_result['failed']}
"""
                )

        except Exception as e:
            st.error(f"Market refresh failed: {e}")