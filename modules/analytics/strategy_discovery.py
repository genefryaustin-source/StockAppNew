import itertools
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from modules.analytics.strategy_service import save_discovered_strategies


FACTOR_COLUMNS = [
    "Quality",
    "Growth",
    "Value",
    "Momentum",
    "Alpha Score",
]


# -----------------------------------------------------
# Helpers
# -----------------------------------------------------

def _extract_close(series_or_df):

    if series_or_df is None:
        return None

    if isinstance(series_or_df, pd.DataFrame):

        if "Close" not in series_or_df.columns:
            return None

        return pd.to_numeric(series_or_df["Close"], errors="coerce").dropna()

    if isinstance(series_or_df, pd.Series):

        return pd.to_numeric(series_or_df, errors="coerce").dropna()

    return None


def _compute_returns(series):

    if series is None or len(series) < 120:
        return None

    r = series.pct_change().dropna()

    if r.empty:
        return None

    return r


def _portfolio_curve(price_cache, symbols):

    rets = []

    for sym in symbols:

        series = _extract_close(price_cache.get(sym))

        r = _compute_returns(series)

        if r is not None:

            r.name = sym

            rets.append(r)

    if not rets:
        return None

    df = pd.concat(rets, axis=1).dropna()

    if df.empty:
        return None

    port_r = df.mean(axis=1)

    curve = (1.0 + port_r).cumprod()

    return curve


def _benchmark_curve(price_cache, benchmark="SPY"):

    series = _extract_close(price_cache.get(benchmark))

    r = _compute_returns(series)

    if r is None:
        return None

    return (1.0 + r).cumprod()


def _max_drawdown(curve):

    if curve is None or len(curve) < 2:
        return None

    peak = curve.cummax()

    dd = (curve - peak) / peak

    return float(dd.min())


def _sharpe(returns):

    if returns is None or returns.empty:
        return None

    vol = returns.std()

    if vol == 0 or pd.isna(vol):
        return None

    return float((returns.mean() / vol) * np.sqrt(252))


def _score_strategy_rows(df, factors):

    work = df.copy()

    usable = [f for f in factors if f in work.columns]

    if not usable:
        return None

    for c in usable:

        work[c] = pd.to_numeric(work[c], errors="coerce")

    work["__strategy_score"] = work[usable].mean(axis=1, skipna=True)

    work = work.dropna(subset=["__strategy_score"])

    if work.empty:
        return None

    return work.sort_values("__strategy_score", ascending=False)


def _build_strategy_name(factors):

    return " + ".join(factors)


# -----------------------------------------------------
# Strategy Discovery
# -----------------------------------------------------

def discover_strategies(rank_rows, price_cache, top_n_holdings=10, max_combo_size=3):

    if rank_rows is None or rank_rows.empty:
        return pd.DataFrame(), {}

    available = [c for c in FACTOR_COLUMNS if c in rank_rows.columns]

    if not available:
        return pd.DataFrame(), {}

    strategy_records = []
    strategy_curves = {}

    combos = []

    for k in range(1, max_combo_size + 1):

        combos.extend(itertools.combinations(available, k))

    for combo in combos:

        scored = _score_strategy_rows(rank_rows, combo)

        if scored is None or scored.empty:
            continue

        ticker_col = "Ticker" if "Ticker" in scored.columns else "Symbol"

        if ticker_col not in scored.columns:
            continue

        symbols = (
            scored[ticker_col]
            .astype(str)
            .str.upper()
            .head(top_n_holdings)
            .tolist()
        )

        curve = _portfolio_curve(price_cache, symbols)

        bench = _benchmark_curve(price_cache)

        if curve is None or bench is None:
            continue

        df = pd.concat(
            [
                curve.rename("Strategy"),
                bench.rename("SPY"),
            ],
            axis=1,
        ).dropna()

        if df.empty:
            continue

        strat_returns = df["Strategy"].pct_change().dropna()

        bench_returns = df["SPY"].pct_change().dropna()

        total_return = float(df["Strategy"].iloc[-1] - 1.0)

        bench_return = float(df["SPY"].iloc[-1] - 1.0)

        sharpe = _sharpe(strat_returns)

        max_dd = _max_drawdown(df["Strategy"])

        alpha = None

        if not strat_returns.empty and not bench_returns.empty:

            alpha = float((strat_returns - bench_returns).mean() * 252)

        name = _build_strategy_name(combo)

        strategy_records.append(
            {
                "Strategy": name,
                "Factors": ", ".join(combo),
                "Holdings": ", ".join(symbols),
                "Return": total_return,
                "SPY Return": bench_return,
                "Alpha": alpha,
                "Sharpe": sharpe,
                "Max Drawdown": max_dd,
            }
        )

        strategy_curves[name] = df

    if not strategy_records:
        return pd.DataFrame(), {}

    out = pd.DataFrame(strategy_records)

    out = out.sort_values(
        by=["Sharpe", "Return", "Alpha"],
        ascending=[False, False, False],
        na_position="last",
    ).reset_index(drop=True)

    return out, strategy_curves


# -----------------------------------------------------
# UI
# -----------------------------------------------------

def render_strategy_discovery(db, user):

    st.subheader("Phase 18 — AI Strategy Discovery")

    rank_rows = st.session_state.get("ai_rank_df")

    if rank_rows is None or not isinstance(rank_rows, pd.DataFrame):

        rank_rows = st.session_state.get("rank_rows")

    price_cache = st.session_state.get("price_cache", {})

    if rank_rows is None or rank_rows.empty:

        st.warning("Run AI Rankings first.")

        return

    if not price_cache:

        st.warning("Market data cache not available.")

        return

    c1, c2 = st.columns(2)

    with c1:

        top_n_holdings = st.slider(
            "Top Holdings Per Strategy",
            3,
            20,
            10,
        )

    with c2:

        max_combo_size = st.slider(
            "Max Factor Combo Size",
            1,
            4,
            3,
        )

    if st.button("Discover Strategies", type="primary"):

        with st.spinner("Testing factor combinations..."):

            summary_df, curves = discover_strategies(
                rank_rows,
                price_cache,
                top_n_holdings,
                max_combo_size,
            )

        if summary_df.empty:

            st.warning("No valid strategies found.")

            return

        st.session_state.discovered_strategies = summary_df

        st.session_state.discovered_strategy_curves = curves

    summary_df = st.session_state.get("discovered_strategies")

    curves = st.session_state.get("discovered_strategy_curves", {})

    if summary_df is None or summary_df.empty:
        return

    st.markdown("### Strategy Leaderboard")

    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    # -------------------------------------------------
    # Save strategies
    # -------------------------------------------------

    if st.button("Save Strategies to Database"):

        inserted = save_discovered_strategies(
            db=db,
            tenant_id=user["tenant_id"],
            df=summary_df,
        )

        st.success(f"{inserted} strategies saved to database.")

    # -------------------------------------------------
    # Strategy chart
    # -------------------------------------------------

    strategy_names = summary_df["Strategy"].tolist()

    selected_strategy = st.selectbox(
        "Inspect Strategy",
        strategy_names,
    )

    if selected_strategy in curves:

        df = curves[selected_strategy]

        fig, ax = plt.subplots()

        ax.plot(df.index, df["Strategy"], label=selected_strategy)

        ax.plot(df.index, df["SPY"], label="SPY")

        ax.legend()

        ax.set_title("Strategy vs SPY")

        st.pyplot(fig)

        row = summary_df[summary_df["Strategy"] == selected_strategy].iloc[0]

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Return", f"{row['Return'] * 100:.2f}%")

        if pd.notna(row["Alpha"]):
            c2.metric("Alpha", f"{row['Alpha']:.4f}")
        else:
            c2.metric("Alpha", "N/A")

        if pd.notna(row["Sharpe"]):
            c3.metric("Sharpe", f"{row['Sharpe']:.2f}")
        else:
            c3.metric("Sharpe", "N/A")

        if pd.notna(row["Max Drawdown"]):
            c4.metric("Max DD", f"{row['Max Drawdown'] * 100:.2f}%")
        else:
            c4.metric("Max DD", "N/A")

        st.caption(f"Holdings: {row['Holdings']}")

