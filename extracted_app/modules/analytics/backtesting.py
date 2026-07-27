import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


# -----------------------------------------------------
# Helpers
# -----------------------------------------------------

MIN_HISTORY = 120


def extract_close(series_or_df):

    if series_or_df is None:
        return None

    if isinstance(series_or_df, pd.DataFrame):

        if "Close" not in series_or_df.columns:
            return None

        return series_or_df["Close"]

    return series_or_df


def compute_returns(series):

    if series is None or len(series) < MIN_HISTORY:
        return None

    returns = series.pct_change().dropna()

    if returns.empty:
        return None

    return returns


# -----------------------------------------------------
# Portfolio Curve
# -----------------------------------------------------

def portfolio_curve(price_cache, symbols):

    returns = []

    for sym in symbols:

        data = price_cache.get(sym)

        series = extract_close(data)

        r = compute_returns(series)

        if r is not None:
            returns.append(r)

    if not returns:
        return None

    df = pd.concat(returns, axis=1)

    df = df.mean(axis=1)

    curve = (1 + df).cumprod()

    return curve


def benchmark_curve(price_cache, benchmark="SPY"):

    data = price_cache.get(benchmark)

    series = extract_close(data)

    r = compute_returns(series)

    if r is None:
        return None

    return (1 + r).cumprod()


# -----------------------------------------------------
# Performance Metrics
# -----------------------------------------------------

def sharpe_ratio(returns):

    if returns.std() == 0:
        return 0

    return (returns.mean() / returns.std()) * np.sqrt(252)


def volatility(returns):

    return returns.std() * np.sqrt(252)


def max_drawdown(curve):

    peak = curve.cummax()

    dd = (curve - peak) / peak

    return dd.min()


def alpha(strategy_returns, benchmark_returns):

    diff = strategy_returns - benchmark_returns

    return diff.mean() * 252


# -----------------------------------------------------
# Backtesting Engine
# -----------------------------------------------------

def render_backtest(rows):

    st.subheader("Strategy Backtesting Engine")

    price_cache = st.session_state.get("price_cache", {})

    # -------------------------------------------
    # Validation
    # -------------------------------------------

    if rows is None or not isinstance(rows, pd.DataFrame) or rows.empty:
        st.warning("Run AI Rankings first.")
        return

    if not price_cache:
        st.warning("Market data cache not available.")
        return

    # -------------------------------------------
    # Strategy Selection
    # -------------------------------------------

    strategy = st.selectbox(
        "Strategy",
        [
            "Momentum",
            "Value",
            "Growth",
            "Quality",
            "Composite",
        ],
    )

    top_n = st.slider("Top N Stocks", 3, 20, 5)

    # -------------------------------------------
    # Column Mapping
    # -------------------------------------------

    col_map = {
        "Momentum": "Momentum",
        "Value": "Value",
        "Growth": "Growth",
        "Quality": "Quality",
        "Composite": "Alpha Score",
    }

    sort_col = col_map[strategy]

    if sort_col not in rows.columns:
        st.warning(f"{sort_col} column not found in rankings.")
        return

    # -------------------------------------------
    # Select Portfolio
    # -------------------------------------------

    sorted_rows = rows.sort_values(sort_col, ascending=False)

    selected = sorted_rows.head(top_n)

    ticker_col = "Ticker" if "Ticker" in selected.columns else "Symbol"

    symbols = selected[ticker_col].tolist()

    st.caption(f"Portfolio: {', '.join(symbols)}")

    # -------------------------------------------
    # Compute Curves
    # -------------------------------------------

    port_curve = portfolio_curve(price_cache, symbols)

    bench_curve = benchmark_curve(price_cache)

    if port_curve is None or bench_curve is None:
        st.warning("Not enough price data for selected symbols.")
        return

    df = pd.concat(
        [
            port_curve.rename("Strategy"),
            bench_curve.rename("SPY"),
        ],
        axis=1,
    ).dropna()

    # -------------------------------------------
    # Plot Performance
    # -------------------------------------------

    fig, ax = plt.subplots()

    ax.plot(df.index, df["Strategy"], label="Strategy")

    ax.plot(df.index, df["SPY"], label="SPY Benchmark")

    ax.legend()

    ax.set_title("Backtest Performance")

    st.pyplot(fig)

    # -------------------------------------------
    # Metrics
    # -------------------------------------------

    strat_returns = df["Strategy"].pct_change().dropna()

    bench_returns = df["SPY"].pct_change().dropna()

    total_return = df.iloc[-1] - 1

    sharpe = sharpe_ratio(strat_returns)

    vol = volatility(strat_returns)

    dd = max_drawdown(df["Strategy"])

    a = alpha(strat_returns, bench_returns)

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Strategy Return", f"{total_return['Strategy']*100:.2f}%")

    c2.metric("SPY Return", f"{total_return['SPY']*100:.2f}%")

    c3.metric("Sharpe Ratio", f"{sharpe:.2f}")

    c4.metric("Volatility", f"{vol:.2f}")

    c5.metric("Max Drawdown", f"{dd*100:.2f}%")

    st.metric("Alpha vs SPY", f"{a:.2f}")

    # -------------------------------------------
    # Display Holdings
    # -------------------------------------------

    st.markdown("### Strategy Holdings")

    st.dataframe(
        selected[[ticker_col, sort_col]],
        use_container_width=True,
    )