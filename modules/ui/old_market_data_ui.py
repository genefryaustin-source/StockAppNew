import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from sqlalchemy import text

from modules.market_data.service import get_price_history
from modules.market_data.updater import update_latest_prices
from modules.analytics.incremental_runner import run_incremental_analytics


# ---------------------------------------------------
# Market Data Viewer
# ---------------------------------------------------

def render_market_data(db, user):

    st.subheader("Market Data")

    col1, col2 = st.columns(2)

    with col1:
        symbol = st.text_input("Symbol", "PLTR").upper()

    with col2:
        load = st.button("Load Data")

    if load:

        df = get_price_history(
            db,
            symbol,
            period="1y",
            interval="1d"
        )

        if df is None or df.empty:
            st.warning("No data found.")
            return

        df = df.copy()
        df["Date"] = pd.to_datetime(df["Date"])

        # ---------------------------------------
        # Candlestick Chart
        # ---------------------------------------

        fig = go.Figure()

        fig.add_trace(
            go.Candlestick(
                x=df["Date"],
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Price"
            )
        )

        # SMA 50
        if len(df) > 50:
            df["SMA50"] = df["Close"].rolling(50).mean()
            fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA50"], name="SMA50"))

        # SMA 200
        if len(df) > 200:
            df["SMA200"] = df["Close"].rolling(200).mean()
            fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA200"], name="SMA200"))

        fig.update_layout(height=500)

        st.plotly_chart(fig, use_container_width=True)

        # ---------------------------------------
        # RSI Indicator
        # ---------------------------------------

        if len(df) > 14:
            delta = df["Close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()
            rs = gain / loss
            df["RSI"] = 100 - (100 / (1 + rs))

            st.subheader("RSI (14)")
            st.line_chart(df.set_index("Date")["RSI"])

        # ---------------------------------------
        # Table with Pagination
        # ---------------------------------------

        st.subheader("Price History")

        page_size = st.selectbox("Rows per page", [100, 250, 500, 1000], index=1)
        page = st.number_input("Page", min_value=1, step=1, value=1)

        start = (page - 1) * page_size
        end = start + page_size

        st.dataframe(df.iloc[start:end], use_container_width=True)
        st.write("Row count:", len(df))
    # ---------------------------------------
    # Data Freshness Check
    # ---------------------------------------

    st.divider()
    st.subheader("Data Freshness (Oldest Updated Symbols)")

    try:
        stale = db.execute(text("""
            SELECT symbol, MAX(date) as last_date
            FROM price_history
            GROUP BY symbol
            ORDER BY last_date ASC
            LIMIT 20
        """)).fetchall()

        if stale:
            st.dataframe(stale, use_container_width=True)
        else:
            st.info("No data available.")

    except Exception as e:
        st.warning(f"Freshness check failed: {e}")


# ---------------------------------------------------
# Market Data Refresh + Auto Analytics
# ---------------------------------------------------

def render_market_refresh(db, user):

    st.subheader("🔄 Market Data Refresh")

    col1, col2 = st.columns(2)

    with col1:
        limit = st.number_input(
            "Limit symbols (0 = all)",
            min_value=0,
            value=0,
            step=100
        )

    with col2:
        run = st.button("Refresh Latest Prices", type="primary")

    if run:

        try:
            # ---------------------------------------
            # Load symbols
            # ---------------------------------------
            query = "SELECT symbol FROM universe_equities"

            if limit > 0:
                query += f" LIMIT {int(limit)}"

            rows = db.execute(text(query)).fetchall()
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

            # ---------------------------------------
            # Run Market Data Update
            # ---------------------------------------
            result = update_latest_prices(
                db,
                symbols,
                progress_callback=progress_callback
            )

            updated_symbols = result.get("updated_symbols", [])

            st.success(f"""
✅ Market Data Refresh Complete

Total: {result['total']}
Updated: {result['updated']}
Skipped: {result['skipped']}
Failed: {result['failed']}
""")

            # ---------------------------------------
            # Auto Analytics (Incremental)
            # ---------------------------------------
            if updated_symbols:

                st.info(f"Running analytics for {len(updated_symbols)} updated symbols...")

                analytics_result = run_incremental_analytics(
                    db,
                    user["tenant_id"],
                    updated_symbols
                )

                st.success(f"""
📊 Analytics Updated

Processed: {analytics_result['processed']}
Failed: {analytics_result['failed']}
""")

        except Exception as e:
            st.error(f"Market refresh failed: {e}")