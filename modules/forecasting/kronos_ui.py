"""
modules/forecasting/kronos_ui.py

"Kronos AI Chart Forecast" — a Streamlit page that reads a stock's
candlesticks (OHLCV) and produces a probabilistic price forecast,
volatility-regime prediction, and direction-confidence score, using the
same approach as the Kronos foundation model's public demo:

  https://github.com/shiyu-coder/Kronos
  https://shiyu-coder.github.io/Kronos-demo/  (BTC/USDT live forecast)

How to wire into app.py
─────────────────────────────────────────────────────────────
Add "Kronos AI Forecast" to the `pages` list (and a NAV_GROUPS entry,
e.g. under "🤖 AI Suite"), then:

    elif page == "Kronos AI Forecast":
        if not check_page(user, "Kronos AI Forecast", db):
            require_page(user, "Kronos AI Forecast", db)
            st.stop()
        try:
            from modules.forecasting.kronos_ui import render_kronos_forecast_page
            run_page("Kronos AI Forecast", render_kronos_forecast_page, db, user)
        except Exception as e:
            safe_rollback(db)
            st.error("Kronos AI Forecast module failed to load.")
            st.exception(e)
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.market_data.service import get_price_history
from modules.forecasting.kronos_engine import (
    KRONOS_MODELS,
    DEFAULT_MODEL_LABEL,
    kronos_status,
    run_kronos_forecast,
)


def render_kronos_forecast_page(db, user):
    st.header("🕯️ Kronos AI Chart Forecast")
    st.caption(
        "Candlestick foundation-model forecasting — price path, volatility regime, "
        "and direction confidence, learned directly from OHLCV bars rather than "
        "text-generated guesses. Not financial advice."
    )
    render_kronos_forecast_panel(db, user)


def render_kronos_forecast_panel(db, user, default_symbol: str = "NVDA"):
    status = kronos_status()
    if not status["available"]:
        st.warning(
            "The real Kronos model isn't installed in this environment "
            f"(missing: {', '.join(status['missing_packages']) or 'weights'}). "
            "Add `torch`, `einops`, `huggingface_hub`, and `safetensors` to "
            "requirements.txt and redeploy to enable it. Showing a statistical "
            "fallback forecast in the meantime so the page still works."
        )
    elif not status["gpu"]:
        st.caption("Running on CPU — Kronos-mini or Kronos-small recommended for speed.")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        symbol = st.text_input("Ticker", value=default_symbol, key="kronos_symbol").upper().strip()
    with c2:
        interval = st.selectbox(
            "Interval", ["1d", "1h", "30m", "15m", "5m"], index=0, key="kronos_interval"
        )
    with c3:
        period = st.selectbox(
            "History window", ["3mo", "6mo", "1y", "2y", "5y"], index=2, key="kronos_period"
        )

    c4, c5, c6, c7 = st.columns([1.4, 1, 1, 1])
    with c4:
        model_label = st.selectbox(
            "Model", list(KRONOS_MODELS.keys()),
            index=list(KRONOS_MODELS.keys()).index(DEFAULT_MODEL_LABEL),
            key="kronos_model_label",
        )
    with c5:
        lookback = st.slider("Lookback bars", 60, KRONOS_MODELS[model_label]["max_context"], 200, key="kronos_lookback")
    with c6:
        pred_len = st.slider("Forecast bars", 5, 90, 24, key="kronos_pred_len")
    with c7:
        n_paths = st.slider("Simulated paths", 5, 50, 20, key="kronos_n_paths")

    with st.expander("Advanced sampling settings"):
        a1, a2 = st.columns(2)
        with a1:
            temperature = st.slider("Temperature (T)", 0.3, 1.5, 1.0, 0.05, key="kronos_temp")
        with a2:
            top_p = st.slider("Top-p", 0.1, 1.0, 0.9, 0.05, key="kronos_top_p")

    run = st.button("Run Kronos Forecast", type="primary", key="kronos_run_btn")

    cache_key = "kronos_last_result"
    if run:
        with st.spinner(f"Loading {symbol} candlesticks and running {n_paths} simulated Kronos paths…"):
            try:
                px = get_price_history(db, symbol, period=period, interval=interval)
                if px is None or px.empty:
                    st.error(f"No price history found for {symbol}.")
                    return
                result = run_kronos_forecast(
                    px,
                    lookback=lookback,
                    pred_len=pred_len,
                    n_paths=n_paths,
                    temperature=temperature,
                    top_p=top_p,
                    model_label=model_label,
                )
                result["_symbol"] = symbol
                result["_history"] = px
                st.session_state[cache_key] = result
            except Exception as e:
                st.error(f"Forecast failed: {e}")
                return

    result = st.session_state.get(cache_key)
    if not result:
        st.info("Set your parameters and click **Run Kronos Forecast**.")
        return

    if result.get("error"):
        st.warning(result["error"])

    engine_badge = "🟢 Kronos foundation model" if result["engine"] == "kronos" else "🟡 Statistical fallback"
    st.caption(f"{engine_badge} · {result['engine_label']} · {result['n_paths']} sampled paths over {result['pred_len']} bars")

    _render_metrics(result)
    _render_chart(result)
    _render_paths_table(result)


def _render_metrics(result: dict) -> None:
    up_prob = result["direction_up_prob"]
    vol_prob = result["vol_elevated_prob"]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Direction confidence",
        f"{up_prob * 100:.0f}% up" if up_prob >= 0.5 else f"{(1 - up_prob) * 100:.0f}% down",
        help="Share of simulated Kronos paths whose final close is above the current price.",
    )
    m2.metric(
        f"Target price (+{result['pred_len']} bars)",
        f"${result['target_price']:.2f}",
        f"{result['target_change_pct']:+.2f}%",
    )
    m3.metric(
        "Predicted volatility (per-bar σ)",
        f"{result['predicted_vol_per_bar'] * 100:.2f}%",
        help="Std. dev. of simulated bar-to-bar returns across all sampled paths.",
    )
    if not np.isnan(vol_prob):
        m4.metric(
            "P(volatility rises)",
            f"{vol_prob * 100:.0f}%",
            help="Share of simulated paths whose forecast volatility exceeds the last 60 bars' realized volatility "
                 f"({result['realized_vol_per_bar'] * 100:.2f}% per-bar).",
        )
    else:
        m4.metric("P(volatility rises)", "n/a")


def _render_chart(result: dict) -> None:
    hist = result["_history"].copy()
    hist.columns = [str(c).strip() for c in hist.columns]
    if "close" in hist.columns and "Close" not in hist.columns:
        hist = hist.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"})
    if "date" in hist.columns and "Date" not in hist.columns:
        hist = hist.rename(columns={"date": "Date"})
    if "Date" not in hist.columns:
        hist = hist.reset_index().rename(columns={hist.index.name or "index": "Date"})
    hist["Date"] = pd.to_datetime(hist["Date"], errors="coerce")
    hist = hist.dropna(subset=["Date", "Close"]).tail(max(result["pred_len"] * 4, 120))

    fdf = result["forecast_df"]
    paths = result["sample_paths_close"]

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=hist["Date"], open=hist.get("Open", hist["Close"]), high=hist.get("High", hist["Close"]),
        low=hist.get("Low", hist["Close"]), close=hist["Close"],
        name="History",
        increasing_line_color="#1D9E75", decreasing_line_color="#E24B4A",
        increasing_fillcolor="#1D9E75", decreasing_fillcolor="#E24B4A",
        line=dict(width=1),
    ))

    if len(hist) > 30:
        try:
            from modules.indicators.signal_suite import compute_signals, add_signal_overlay
            sig_df = compute_signals(hist)
            add_signal_overlay(fig, sig_df, row=None, col=None, show_ribbon=False)
        except Exception:
            pass

    # Faint spaghetti of individual sampled paths (up to 15 for readability).
    for i in range(min(15, paths.shape[0])):
        fig.add_trace(go.Scatter(
            x=fdf["timestamps"], y=paths[i],
            mode="lines", line=dict(width=0.7, color="rgba(120,140,255,0.25)"),
            showlegend=False, hoverinfo="skip",
        ))

    # Uncertainty band (p10-p90).
    fig.add_trace(go.Scatter(
        x=pd.concat([fdf["timestamps"], fdf["timestamps"][::-1]]),
        y=pd.concat([fdf["p90"], fdf["p10"][::-1]]),
        fill="toself", fillcolor="rgba(255,165,0,0.15)",
        line=dict(color="rgba(255,255,255,0)"),
        name="10th–90th pct range", hoverinfo="skip",
    ))

    # Mean forecast path.
    fig.add_trace(go.Scatter(
        x=fdf["timestamps"], y=fdf["close"],
        mode="lines+markers", line=dict(width=2.5, color="#FFA500"),
        name="Kronos mean forecast",
    ))

    fig.update_layout(
        height=520,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=10, r=10, t=30, b=10),
        template="plotly_dark",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_paths_table(result: dict) -> None:
    with st.expander("Forecast detail (mean OHLC + uncertainty band)"):
        st.dataframe(
            result["forecast_df"].rename(columns={
                "timestamps": "Date", "open": "Open", "high": "High",
                "low": "Low", "close": "Close", "p10": "P10", "p90": "P90",
            }).round(2),
            use_container_width=True,
            hide_index=True,
        )
