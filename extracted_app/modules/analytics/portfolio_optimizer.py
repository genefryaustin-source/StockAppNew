import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def _build_return_matrix(price_cache, symbols):
    series_list = []

    for sym in symbols:
        s = price_cache.get(sym)

        if s is None or len(s) < 30:
            continue

        r = pd.Series(s).pct_change().dropna()
        r.name = sym
        series_list.append(r)

    if not series_list:
        return None

    returns = pd.concat(series_list, axis=1).dropna()

    if returns.empty or returns.shape[1] < 2:
        return None

    return returns


def _portfolio_stats(weights, mean_returns, cov_matrix, rf=0.0):
    port_return = np.sum(mean_returns * weights) * 252
    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix * 252, weights)))

    if port_vol == 0:
        sharpe = 0.0
    else:
        sharpe = (port_return - rf) / port_vol

    return port_return, port_vol, sharpe


def _random_weight_matrix(n_assets, n_portfolios=5000):
    weights = np.random.random((n_portfolios, n_assets))
    weights = weights / weights.sum(axis=1, keepdims=True)
    return weights


def optimize_max_sharpe(returns, n_portfolios=5000, rf=0.0):
    mean_returns = returns.mean().values
    cov_matrix = returns.cov().values
    tickers = list(returns.columns)

    weight_matrix = _random_weight_matrix(len(tickers), n_portfolios=n_portfolios)

    best = None
    records = []

    for w in weight_matrix:
        port_return, port_vol, sharpe = _portfolio_stats(w, mean_returns, cov_matrix, rf=rf)

        rec = {
            "Return": port_return,
            "Volatility": port_vol,
            "Sharpe": sharpe,
            **{tickers[i]: w[i] for i in range(len(tickers))}
        }
        records.append(rec)

        if best is None or sharpe > best["Sharpe"]:
            best = rec

    frontier = pd.DataFrame(records)
    return best, frontier


def optimize_min_volatility(returns, n_portfolios=5000, rf=0.0):
    mean_returns = returns.mean().values
    cov_matrix = returns.cov().values
    tickers = list(returns.columns)

    weight_matrix = _random_weight_matrix(len(tickers), n_portfolios=n_portfolios)

    best = None
    records = []

    for w in weight_matrix:
        port_return, port_vol, sharpe = _portfolio_stats(w, mean_returns, cov_matrix, rf=rf)

        rec = {
            "Return": port_return,
            "Volatility": port_vol,
            "Sharpe": sharpe,
            **{tickers[i]: w[i] for i in range(len(tickers))}
        }
        records.append(rec)

        if best is None or port_vol < best["Volatility"]:
            best = rec

    frontier = pd.DataFrame(records)
    return best, frontier


def optimize_risk_parity(returns):
    vol = returns.std() * np.sqrt(252)
    inv_vol = 1 / vol.replace(0, np.nan)
    inv_vol = inv_vol.dropna()

    if inv_vol.empty:
        return None

    weights = inv_vol / inv_vol.sum()

    cov = returns[weights.index].cov().values
    mean_returns = returns[weights.index].mean().values
    w = weights.values

    port_return, port_vol, sharpe = _portfolio_stats(w, mean_returns, cov)

    result = {
        "Return": port_return,
        "Volatility": port_vol,
        "Sharpe": sharpe,
        **{weights.index[i]: w[i] for i in range(len(weights.index))}
    }

    return result


def _weights_to_df(opt_result):
    if opt_result is None:
        return pd.DataFrame()

    rows = []
    for k, v in opt_result.items():
        if k in {"Return", "Volatility", "Sharpe"}:
            continue
        rows.append({"Ticker": k, "Weight": v})

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values("Weight", ascending=False).reset_index(drop=True)
    return df


def render_portfolio_optimizer(rows):
    st.subheader("Portfolio Optimizer")

    price_cache = st.session_state.get("price_cache", {})

    if rows is None or not isinstance(rows, pd.DataFrame) or rows.empty:
        st.warning("Run AI Rankings first.")
        return

    if not price_cache:
        st.warning("Market data cache not available.")
        return

    if "Ticker" not in rows.columns:
        st.warning("Ticker column missing from rankings.")
        return

    universe_size = st.slider("Optimizer Universe Size", 3, min(20, len(rows)), min(5, len(rows)))
    method = st.selectbox(
        "Optimization Method",
        ["Max Sharpe", "Min Volatility", "Risk Parity"],
    )

    top = rows.head(universe_size).copy()
    symbols = top["Ticker"].dropna().astype(str).str.upper().tolist()

    returns = _build_return_matrix(price_cache, symbols)

    if returns is None or returns.empty:
        st.warning("Not enough overlapping price history for optimization.")
        return

    if method == "Max Sharpe":
        best, frontier = optimize_max_sharpe(returns)
    elif method == "Min Volatility":
        best, frontier = optimize_min_volatility(returns)
    else:
        best = optimize_risk_parity(returns)
        frontier = None

    if best is None:
        st.warning("Optimization failed.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Expected Return", f"{best['Return']*100:.2f}%")
    c2.metric("Volatility", f"{best['Volatility']*100:.2f}%")
    c3.metric("Sharpe Ratio", f"{best['Sharpe']:.2f}")

    weights_df = _weights_to_df(best)

    st.markdown("### Optimal Weights")
    st.dataframe(weights_df, use_container_width=True, hide_index=True)

    if not weights_df.empty:
        fig, ax = plt.subplots()
        ax.pie(
            weights_df["Weight"],
            labels=weights_df["Ticker"],
            autopct="%1.1f%%",
            startangle=90,
        )
        ax.axis("equal")
        st.pyplot(fig)

    if frontier is not None and not frontier.empty:
        st.markdown("### Efficient Frontier (Sampled)")
        fig2, ax2 = plt.subplots()
        ax2.scatter(frontier["Volatility"], frontier["Return"], alpha=0.25)
        ax2.scatter(best["Volatility"], best["Return"], marker="*", s=250)
        ax2.set_xlabel("Volatility")
        ax2.set_ylabel("Expected Return")
        ax2.set_title("Portfolio Opportunity Set")
        st.pyplot(fig2)

def build_alpha_optimized_portfolio(
    alpha_df,
    method="alpha_weighted",
    max_weight=0.10,
    min_weight=0.01,
    risk_adjust=True,
):
    """
    Converts alpha model output into portfolio weights
    compatible with construction_engine.
    """

    if alpha_df is None or alpha_df.empty:
        return None

    df = alpha_df.copy()

    # ---------------------------
    # BASE SCORE
    # ---------------------------
    df["score"] = df["alpha_score"].clip(lower=0)

    # ---------------------------
    # RISK ADJUSTMENT
    # ---------------------------
    if risk_adjust and "risk_z" in df.columns:
        df["risk_adj"] = 1 / (1 + df["risk_z"].clip(lower=0))
        df["score"] = df["score"] * df["risk_adj"]

    # ---------------------------
    # NORMALIZE
    # ---------------------------
    total = df["score"].sum()

    if total == 0:
        df["weight"] = 1 / len(df)
    else:
        df["weight"] = df["score"] / total

    # ---------------------------
    # CONSTRAINTS
    # ---------------------------
    df["weight"] = df["weight"].clip(lower=min_weight, upper=max_weight)

    # re-normalize
    df["weight"] = df["weight"] / df["weight"].sum()

    return df[[
        "symbol",
        "sector",
        "alpha_score",
        "weight"
    ]]