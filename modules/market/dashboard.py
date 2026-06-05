import streamlit as st
import pandas as pd
from modules.market_data.service import get_price_history
import numpy as np
from modules.market.macro_dashboard import render_macro_dashboard
from sqlalchemy import text

MARKET_UNIVERSE = [
    "AAPL","MSFT","NVDA","AMZN","META",
    "GOOGL","TSLA","JPM","XOM","AVGO"
]


def render_market_dashboard(db):

    try:
        render_macro_dashboard(db)
    except Exception as e:
        st.warning(f"Macro dashboard unavailable: {e}")

    st.divider()

    st.subheader("Top Movers")




    try:

        count = db.execute(
            text("SELECT COUNT(*) FROM price_history")
        ).scalar()

        st.write("PRICE HISTORY ROWS:", count)

    except Exception as e:

        try:
            db.rollback()
        except Exception:
            pass

        st.error(f"PRICE HISTORY ERROR: {repr(e)}")
        st.stop()

    rows_out = []

    for r in rows:

        if not r.previous_price:
            continue

        change_pct = (
                             (float(r.current_price) - float(r.previous_price))
                             / float(r.previous_price)
                     ) * 100.0

        rows_out.append({
            "Ticker": r.symbol,
            "Price": round(float(r.current_price), 2),
            "Change %": round(change_pct, 2),
        })

    df = pd.DataFrame(rows_out)

    if df.empty:
        st.warning("No market history available.")
        return

    gainers = df.sort_values(
        "Change %",
        ascending=False
    ).head(10)

    losers = df.sort_values(
        "Change %",
        ascending=True
    ).head(10)



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
