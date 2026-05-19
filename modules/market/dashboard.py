import streamlit as st
import pandas as pd
from modules.market_data.service import get_price_history
import numpy as np
MARKET_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META",
    "GOOGL","TSLA","JPM","XOM","AVGO"
]


def render_market_dashboard(db):

    st.subheader("Top Movers")



    from modules.market_data.service import get_price_history

    price_cache = {}

    for sym in MARKET_UNIVERSE:
        try:
            df = get_price_history(db, sym, period="1mo")

            if df is not None and not df.empty:

                col = None
                for c in ["close", "Close", "adj_close", "Adj Close"]:
                    if c in df.columns:
                        col = c
                        break

                if col:
                    price_cache[sym] = df[col]
                else:
                    print(f"⚠️ No price column for {sym}: {df.columns}")

        except Exception as e:
            print(f"Market data error for {sym}:", e)

    print("🔥 PRICE CACHE SIZE:", len(price_cache))

    rows = []

    for ticker, series in price_cache.items():

        if series is None or len(series) < 2:
            continue

        last_px = float(series.iloc[-1])
        prev_px = float(series.iloc[-2])

        if prev_px == 0:
            continue

        change_pct = ((last_px / prev_px) - 1.0) * 100

        rows.append({
            "Ticker": ticker,
            "Price": last_px,
            "Change %": change_pct,
        })

    df = pd.DataFrame(rows)

    if df.empty:
        st.warning("Market data unavailable.")
        return

    gainers = df.sort_values("Change %", ascending=False).head(10)
    losers = df.sort_values("Change %", ascending=True).head(10)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Top Gainers")
        st.dataframe(gainers, use_container_width=True)

    with col2:
        st.markdown("### Top Losers")
        st.dataframe(losers, use_container_width=True)

    st.divider()
    st.markdown("## 🔥 Market Heatmap")


    if not df.empty:
        heat_df = df.copy()

        # Normalize change %
        heat_df["Normalized"] = (
                                        heat_df["Change %"] - heat_df["Change %"].min()
                                ) / (heat_df["Change %"].max() - heat_df["Change %"].min() + 1e-9)

        st.dataframe(
            heat_df[["Ticker", "Change %"]],
            use_container_width=True,
            hide_index=True
        )

        def color_scale(val):
            if val > 0:
                return "background-color: rgba(0, 200, 0, 0.3)"
            elif val < 0:
                return "background-color: rgba(200, 0, 0, 0.3)"
            return ""

        st.dataframe(
            df.style.applymap(color_scale, subset=["Change %"]),
            use_container_width=True
        )

        def color_scale(val):
            if val > 0:
                return "background-color: rgba(0, 200, 0, 0.3)"
            elif val < 0:
                return "background-color: rgba(200, 0, 0, 0.3)"
            return ""

        st.dataframe(
            df.style.applymap(color_scale, subset=["Change %"]),
            use_container_width=True
        )