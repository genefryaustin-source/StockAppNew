import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


SECTOR_MAP = {
    "Technology": ["AAPL","MSFT","NVDA"],
    "Financials": ["JPM","BAC"],
    "Healthcare": ["UNH","LLY"],
    "Energy": ["XOM","CVX"],
    "Consumer": ["AMZN","HD"],
    "Industrials": ["CAT","GE"],
}


def _compute_return(series, days=20):

    if series is None or len(series) <= days:
        return None

    last = series.iloc[-1]
    prev = series.iloc[-days]

    if prev == 0:
        return None

    return ((last / prev) - 1) * 100


def render_market_regime(price_cache):

    st.subheader("Market Regime Dashboard")

    if not price_cache:
        st.warning("Market data unavailable")
        return

    # ------------------------------------------------
    # MARKET TREND
    # ------------------------------------------------

    spy = price_cache.get("SPY")

    if spy is not None and len(spy) > 200:

        ma50 = spy.rolling(50).mean().iloc[-1]
        ma200 = spy.rolling(200).mean().iloc[-1]
        last = spy.iloc[-1]

        if last > ma50 > ma200:
            trend = "Strong Bull Trend"
        elif last > ma50:
            trend = "Bullish"
        elif last < ma50 and ma50 > ma200:
            trend = "Correction"
        else:
            trend = "Bearish"

    else:
        trend = "Unknown"

    # ------------------------------------------------
    # MARKET BREADTH
    # ------------------------------------------------

    advances = 0
    declines = 0

    for sym, series in price_cache.items():

        if len(series) < 2:
            continue

        if series.iloc[-1] > series.iloc[-2]:
            advances += 1
        else:
            declines += 1

    breadth = advances - declines

    # ------------------------------------------------
    # MOMENTUM LEADERS
    # ------------------------------------------------

    momentum = []

    for sym, series in price_cache.items():

        r = _compute_return(series, 20)

        if r is None:
            continue

        momentum.append({
            "Symbol": sym,
            "Momentum": r
        })

    momentum_df = pd.DataFrame(momentum)

    if not momentum_df.empty:
        momentum_df = momentum_df.sort_values("Momentum", ascending=False)

    # ------------------------------------------------
    # SECTOR ROTATION
    # ------------------------------------------------

    sector_rows = []

    for sector, tickers in SECTOR_MAP.items():

        vals = []

        for t in tickers:

            series = price_cache.get(t)

            r = _compute_return(series, 20)

            if r is not None:
                vals.append(r)

        if vals:
            sector_rows.append({
                "Sector": sector,
                "Return": sum(vals) / len(vals)
            })

    sector_df = pd.DataFrame(sector_rows)

    if not sector_df.empty:
        sector_df = sector_df.sort_values("Return", ascending=False)

    # ------------------------------------------------
    # DISPLAY
    # ------------------------------------------------

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Market Trend", trend)

    with c2:
        st.metric("Market Breadth", breadth)

    with c3:
        if not momentum_df.empty:
            leader = momentum_df.iloc[0]
            st.metric("Momentum Leader", leader["Symbol"], f"{leader['Momentum']:.2f}%")

    st.divider()

    # ------------------------------------------------
    # SECTOR ROTATION CHART
    # ------------------------------------------------

    if not sector_df.empty:

        fig, ax = plt.subplots()

        ax.bar(sector_df["Sector"], sector_df["Return"])

        plt.xticks(rotation=45)

        ax.set_title("Sector Momentum (20D)")

        st.pyplot(fig)

    # ------------------------------------------------
    # MOMENTUM LEADERS
    # ------------------------------------------------

    if not momentum_df.empty:

        st.markdown("### Momentum Leaders")

        st.dataframe(
            momentum_df.head(10),
            use_container_width=True
        )