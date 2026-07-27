import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


# Sector leaders used for visualization
SECTOR_MAP = {
    "Technology": ["AAPL", "MSFT", "NVDA", "AMD"],
    "Financials": ["JPM", "BAC", "GS"],
    "Healthcare": ["UNH", "LLY", "PFE"],
    "Energy": ["XOM", "CVX"],
    "Consumer": ["AMZN", "HD", "MCD"],
    "Industrials": ["CAT", "GE", "BA"],
}


def render_market_heatmap(price_cache):

    st.subheader("Market Heatmap")

    rows = []

    for sector, tickers in SECTOR_MAP.items():

        for ticker in tickers:

            series = price_cache.get(ticker)

            if series is None or len(series) < 2:
                continue

            last_px = float(series.iloc[-1])
            prev_px = float(series.iloc[-2])

            if prev_px == 0:
                continue

            change_pct = ((last_px / prev_px) - 1) * 100

            rows.append({
                "Sector": sector,
                "Symbol": ticker,
                "Change": change_pct,
            })

    if not rows:

        st.warning("Heatmap data unavailable")
        return

    df = pd.DataFrame(rows)

    sectors = df["Sector"].unique()

    fig, ax = plt.subplots(figsize=(10, 6))

    y = 0

    for sector in sectors:

        sdf = df[df["Sector"] == sector]

        x = 0

        for _, row in sdf.iterrows():

            color = "green" if row["Change"] > 0 else "red"

            ax.add_patch(
                plt.Rectangle(
                    (x, y),
                    1,
                    1,
                    color=color,
                    alpha=0.6
                )
            )

            ax.text(
                x + 0.5,
                y + 0.5,
                f"{row['Symbol']}\n{row['Change']:.1f}%",
                ha="center",
                va="center",
                fontsize=8,
                color="white"
            )

            x += 1

        y += 1

    ax.set_xlim(0, 6)
    ax.set_ylim(0, len(sectors))

    ax.set_xticks([])
    ax.set_yticks(range(len(sectors)))
    ax.set_yticklabels(sectors)

    ax.set_title("Market Sector Heatmap")

    st.pyplot(fig)