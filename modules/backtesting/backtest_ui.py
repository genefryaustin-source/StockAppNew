"""
modules/backtesting/backtest_ui.py

"Signal Backtester" page -- runs modules.backtesting.vectorbt_engine
against a symbol, either using the app's own Buy/Sell/TP signal logic
(modules.indicators.signal_suite, the same one drawn on every chart) or a
simple MA crossover baseline for comparison.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.backtesting.vectorbt_engine import (
    vectorbt_available, backtest_signal_suite_strategy, backtest_ma_crossover,
)


def render_backtest_page(db, user):
    st.header("🧪 Signal Backtester")
    st.caption(
        "Backtests the same Buy/Sell/TP signal logic shown on charts app-wide "
        "(modules.indicators.signal_suite), or a simple MA crossover baseline for comparison. "
        "Powered by vectorbt."
    )

    if not vectorbt_available():
        st.warning("vectorbt isn't installed in this environment. Add it to requirements.txt to enable this page.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        symbol = st.text_input("Symbol", value="AAPL", key="bt_symbol").upper().strip()
    with c2:
        period = st.selectbox("History window", ["6mo", "1y", "2y", "5y"], index=2, key="bt_period")
    with c3:
        strategy = st.selectbox("Strategy", ["Signal Suite (app default)", "MA Crossover (baseline)"], key="bt_strategy")

    c4, c5 = st.columns(2)
    with c4:
        init_cash = st.number_input("Starting cash", value=100_000.0, step=10_000.0, key="bt_cash")
    with c5:
        fees = st.slider("Per-trade fee (%)", 0.0, 1.0, 0.1, 0.05, key="bt_fees") / 100.0

    if st.button("▶ Run Backtest", type="primary", key="bt_run"):
        with st.spinner(f"Backtesting {symbol}…"):
            if strategy.startswith("Signal Suite"):
                result = backtest_signal_suite_strategy(db, symbol, period=period, init_cash=init_cash, fees=fees)
            else:
                result = backtest_ma_crossover(db, symbol, period=period, init_cash=init_cash, fees=fees)
            st.session_state["bt_result"] = result

    result = st.session_state.get("bt_result")
    if not result:
        st.info("Set your parameters and click Run Backtest.")
        return

    if not result.get("available"):
        st.error(result.get("reason", "Backtest unavailable."))
        return

    st.caption(f"**{result['strategy']}** on {result['symbol']} — {result['num_signals']} signal(s) fired")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Return", f"{result['total_return']:.1%}",
               f"vs buy & hold {result['benchmark_return']:.1%}")
    m2.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}" if result['sharpe_ratio'] is not None else "n/a")
    m3.metric("Max Drawdown", f"{result['max_drawdown']:.1%}")
    m4.metric("Trades", result["num_trades"],
               f"{result['win_rate']:.0%} win rate" if result.get("win_rate") is not None else None)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=result["equity_curve"].index, y=result["equity_curve"].values,
                              name="Strategy Equity", line=dict(color="#1D9E75", width=2)))
    fig.update_layout(height=380, template="plotly_dark", margin=dict(l=10, r=10, t=30, b=10),
                       title="Equity Curve")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Full stats"):
        st.dataframe(pd.DataFrame(result["stats"].items(), columns=["Metric", "Value"]),
                     use_container_width=True, hide_index=True)
