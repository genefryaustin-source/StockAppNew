import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


SECTOR_MAP = {
    "Technology": ["AAPL", "MSFT", "NVDA"],
    "Financials": ["JPM", "BAC"],
    "Healthcare": ["UNH", "LLY"],
    "Energy": ["XOM", "CVX"],
    "Consumer": ["AMZN", "HD"],
    "Industrials": ["CAT", "GE"],
}


def render_sector_heatmap(price_cache):
    st.subheader("Sector Performance")

    rows = []

    for sector, tickers in SECTOR_MAP.items():
        returns = []

        for ticker in tickers:
            series = price_cache.get(ticker)
            if series is None or len(series) < 2:
                continue

            last_px = float(series.iloc[-1])
            prev_px = float(series.iloc[-2])

            if prev_px == 0:
                continue

            ret = (last_px / prev_px) - 1.0
            returns.append(ret)

        if returns:
            rows.append({
                "Sector": sector,
                "Return": sum(returns) / len(returns),
            })

    if not rows:
        st.warning("Sector data unavailable")
        return

    df = pd.DataFrame(rows).sort_values("Return", ascending=False)

    fig, ax = plt.subplots()
    ax.bar(df["Sector"], df["Return"])
    plt.xticks(rotation=45)
    st.pyplot(fig)

    st.dataframe(df, use_container_width=True)