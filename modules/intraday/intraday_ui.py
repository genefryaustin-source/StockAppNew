"""
modules/intraday/intraday_ui.py

Intraday / Multi-Timeframe Chart — Streamlit UI.

Features:
  - Timeframe selector: 1m, 5m, 15m, 30m, 1h, 4h, 1D, 1W
  - Interactive Plotly candlestick (zoom, pan, hover)
  - Volume bars
  - Overlay indicators: EMA 9/21/50, VWAP (intraday), Bollinger Bands
  - RSI panel
  - MACD panel
  - Auto-refresh toggle for 1m/5m charts
  - Data source badge (MarketData.app / Polygon / Alpaca)
  - Export as CSV / PNG

Embeds into Stock Dashboard via render_intraday_chart(db, user, ticker)

Add to app.py:
    elif page == "Intraday Charts":
        from modules.intraday.intraday_ui import render_intraday_page
        render_intraday_page(db, user)
"""

from __future__ import annotations

import time
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from modules.intraday.intraday_service import (
    TIMEFRAMES,
    get_available_intervals,
    get_intraday_data,
)


# ─────────────────────────────────────────────────────────────
# Indicator calculations
# ─────────────────────────────────────────────────────────────

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _vwap(df: pd.DataFrame) -> pd.Series:
    """VWAP resets at midnight UTC each day."""
    df = df.copy()
    df["_date"] = df["Date"].dt.date
    df["_tp"]   = (df["High"] + df["Low"] + df["Close"]) / 3
    df["_cum_vol"]  = df.groupby("_date")["Volume"].cumsum()
    df["_cum_tpvol"]= df.groupby("_date").apply(
        lambda g: (g["_tp"] * g["Volume"]).cumsum()
    ).reset_index(level=0, drop=True)
    return df["_cum_tpvol"] / df["_cum_vol"].replace(0, float("nan"))


def _bollinger(series: pd.Series, period: int = 20,
               std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid   = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    return mid - std * sigma, mid, mid + std * sigma


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta  = series.diff()
    gain   = delta.clip(lower=0).rolling(period).mean()
    loss   = (-delta.clip(upper=0)).rolling(period).mean()
    rs     = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series,
          fast: int = 12, slow: int = 26,
          signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
    macd_line   = _ema(series, fast) - _ema(series, slow)
    signal_line = _ema(macd_line, signal)
    histogram   = macd_line - signal_line
    return macd_line, signal_line, histogram


# ─────────────────────────────────────────────────────────────
# Chart builder
# ─────────────────────────────────────────────────────────────

def _build_chart(
    df: pd.DataFrame,
    symbol: str,
    interval: str,
    source: str,
    show_ema: bool = True,
    ema_periods: list = None,
    show_vwap: bool = True,
    show_bb: bool = False,
    show_rsi: bool = True,
    show_macd: bool = False,
) -> go.Figure:

    ema_periods = ema_periods or [9, 21, 50]
    is_intraday = interval not in ("1d", "1w")

    # Determine subplot layout
    n_panels  = 1  # price
    n_panels += 1  # volume always
    if show_rsi:
        n_panels += 1
    if show_macd:
        n_panels += 1

    row_heights = [0.55, 0.12]
    specs       = [[{"secondary_y": False}]] * 2
    if show_rsi:
        row_heights.append(0.16)
        specs.append([{"secondary_y": False}])
    if show_macd:
        row_heights.append(0.17)
        specs.append([{"secondary_y": False}])

    subplot_titles = [f"{symbol} — {TIMEFRAMES[interval]['label']}", "Volume"]
    if show_rsi:
        subplot_titles.append("RSI (14)")
    if show_macd:
        subplot_titles.append("MACD (12,26,9)")

    fig = make_subplots(
        rows=n_panels, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # ── Candlestick ───────────────────────────────────────────
    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="Price",
        increasing_line_color="#1D9E75",
        decreasing_line_color="#E24B4A",
        increasing_fillcolor="#1D9E75",
        decreasing_fillcolor="#E24B4A",
        line=dict(width=1),
    ), row=1, col=1)

    # ── EMAs ─────────────────────────────────────────────────
    ema_colors = ["#FFC107", "#2196F3", "#9C27B0"]
    if show_ema:
        for period, color in zip(ema_periods, ema_colors):
            if len(df) > period:
                ema_vals = _ema(df["Close"], period)
                fig.add_trace(go.Scatter(
                    x=df["Date"], y=ema_vals,
                    name=f"EMA {period}",
                    line=dict(color=color, width=1.2),
                    hovertemplate=f"EMA{period}: %{{y:.2f}}<extra></extra>",
                ), row=1, col=1)

    # ── VWAP (intraday only) ──────────────────────────────────
    if show_vwap and is_intraday and len(df) > 5:
        try:
            vwap_vals = _vwap(df)
            fig.add_trace(go.Scatter(
                x=df["Date"], y=vwap_vals,
                name="VWAP",
                line=dict(color="#FF6B9D", width=1.5, dash="dot"),
                hovertemplate="VWAP: %{y:.2f}<extra></extra>",
            ), row=1, col=1)
        except Exception:
            pass

    # ── Bollinger Bands ───────────────────────────────────────
    if show_bb and len(df) > 20:
        bb_lo, bb_mid, bb_hi = _bollinger(df["Close"])
        for vals, name, style in [
            (bb_hi,  "BB Upper", dict(color="#378ADD", width=1, dash="dash")),
            (bb_mid, "BB Mid",   dict(color="#378ADD", width=0.8)),
            (bb_lo,  "BB Lower", dict(color="#378ADD", width=1, dash="dash")),
        ]:
            fig.add_trace(go.Scatter(
                x=df["Date"], y=vals, name=name,
                line=style, opacity=0.6,
                hovertemplate=f"{name}: %{{y:.2f}}<extra></extra>",
            ), row=1, col=1)
        # Fill
        fig.add_trace(go.Scatter(
            x=pd.concat([df["Date"], df["Date"][::-1]]),
            y=pd.concat([bb_hi, bb_lo[::-1]]),
            fill="toself", fillcolor="rgba(55,138,221,0.05)",
            line=dict(color="rgba(0,0,0,0)"), showlegend=False,
            name="BB Fill",
        ), row=1, col=1)

    # ── Volume bars ───────────────────────────────────────────
    colors = ["#1D9E75" if c >= o else "#E24B4A"
              for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df["Date"], y=df["Volume"],
        name="Volume",
        marker_color=colors,
        opacity=0.7,
        hovertemplate="Vol: %{y:,.0f}<extra></extra>",
    ), row=2, col=1)

    cur_row = 3

    # ── RSI panel ─────────────────────────────────────────────
    if show_rsi and len(df) > 15:
        rsi_vals = _rsi(df["Close"])
        fig.add_trace(go.Scatter(
            x=df["Date"], y=rsi_vals,
            name="RSI",
            line=dict(color="#FFD700", width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ), row=cur_row, col=1)
        # Overbought/oversold lines
        for level, color in [(70, "rgba(226,75,74,0.3)"), (30, "rgba(29,158,117,0.3)")]:
            fig.add_hline(y=level, line_dash="dot", line_color=color,
                          row=cur_row, col=1)
        # Fill overbought/oversold zones
        fig.add_hrect(y0=70, y1=100, fillcolor="rgba(226,75,74,0.05)",
                      line_width=0, row=cur_row, col=1)
        fig.add_hrect(y0=0, y1=30, fillcolor="rgba(29,158,117,0.05)",
                      line_width=0, row=cur_row, col=1)
        cur_row += 1

    # ── MACD panel ────────────────────────────────────────────
    if show_macd and len(df) > 30:
        macd_line, signal_line, histogram = _macd(df["Close"])
        hist_colors = ["#1D9E75" if v >= 0 else "#E24B4A" for v in histogram.fillna(0)]

        fig.add_trace(go.Bar(
            x=df["Date"], y=histogram,
            name="MACD Hist",
            marker_color=hist_colors,
            opacity=0.7,
            hovertemplate="Hist: %{y:.3f}<extra></extra>",
        ), row=cur_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=macd_line,
            name="MACD",
            line=dict(color="#2196F3", width=1.5),
            hovertemplate="MACD: %{y:.3f}<extra></extra>",
        ), row=cur_row, col=1)
        fig.add_trace(go.Scatter(
            x=df["Date"], y=signal_line,
            name="Signal",
            line=dict(color="#FF9800", width=1.2),
            hovertemplate="Signal: %{y:.3f}<extra></extra>",
        ), row=cur_row, col=1)

    # ── Layout ────────────────────────────────────────────────
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0F1117",
        plot_bgcolor="#161B22",
        margin=dict(l=0, r=40, t=30, b=20),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.01,
            xanchor="left", x=0,
            bgcolor="rgba(0,0,0,0)",
            font=dict(size=10, color="#8B949E"),
        ),
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        height=620 if (show_rsi or show_macd) else 480,
        font=dict(color="#8B949E", size=10),
    )

    # Style all axes
    axis_style = dict(
        gridcolor="#21262D", gridwidth=0.4,
        linecolor="#30363D",
        tickfont=dict(size=9, color="#8B949E"),
        showgrid=True,
    )
    for i in range(1, n_panels + 1):
        fig.update_xaxes(axis_style, row=i, col=1)
        fig.update_yaxes(axis_style, row=i, col=1)

    # Source watermark
    fig.add_annotation(
        text=f"Source: {source.upper()}",
        xref="paper", yref="paper",
        x=0.01, y=0.01, showarrow=False,
        font=dict(size=8, color="#4A5568"),
        opacity=0.5,
    )

    return fig


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_intraday_page(db, user: dict):
    st.header("📈 Intraday & Multi-Timeframe Charts")
    st.caption(
        "1-minute to weekly charts · EMA · VWAP · Bollinger Bands · RSI · MACD · "
        "Powered by MarketData.app → Polygon → Alpaca"
    )

    if not PLOTLY_AVAILABLE:
        st.error("Plotly is required for intraday charts. Run: `pip install plotly`")
        return

    # ── Controls ──────────────────────────────────────────────
    col_sym, col_tf, col_ref = st.columns([2, 2, 1])
    with col_sym:
        ticker = st.text_input(
            "Symbol", value=st.session_state.get("intraday_ticker", "SPY"),
            key="intraday_ticker_input",
            placeholder="SPY, NVDA, AAPL…",
        ).upper().strip()
    with col_tf:
        intervals = get_available_intervals()
        tf_labels  = [i["label"] for i in intervals]
        tf_values  = [i["value"] for i in intervals]
        default_idx = tf_values.index("5m") if "5m" in tf_values else 1
        selected_tf = st.selectbox(
            "Timeframe",
            options=tf_values,
            format_func=lambda x: next(i["label"] for i in intervals if i["value"] == x),
            index=st.session_state.get("intraday_tf_idx", default_idx),
            key="intraday_tf",
        )
    with col_ref:
        st.write("")
        refresh = st.button("↺ Refresh", key="intraday_refresh",
                            use_container_width=True)

    # ── Indicator toggles ─────────────────────────────────────
    with st.expander("📐 Indicators", expanded=False):
        col_i1, col_i2, col_i3, col_i4, col_i5 = st.columns(5)
        with col_i1:
            show_ema  = st.checkbox("EMA 9/21/50", value=True, key="ind_ema")
        with col_i2:
            show_vwap = st.checkbox("VWAP", value=True, key="ind_vwap")
        with col_i3:
            show_bb   = st.checkbox("Bollinger Bands", value=False, key="ind_bb")
        with col_i4:
            show_rsi  = st.checkbox("RSI", value=True, key="ind_rsi")
        with col_i5:
            show_macd = st.checkbox("MACD", value=False, key="ind_macd")

    if not ticker:
        st.info("Enter a ticker symbol to load the chart.")
        return

    # ── Auto-refresh for fast timeframes ─────────────────────
    is_fast = selected_tf in ("1m", "5m")
    if is_fast:
        col_ar, col_ari = st.columns([1, 3])
        with col_ar:
            auto_refresh = st.checkbox("Auto-refresh", value=False, key="intraday_auto")
        with col_ari:
            if auto_refresh:
                refresh_secs = {"1m": 30, "5m": 60}.get(selected_tf, 60)
                st.caption(f"⏱ Refreshing every {refresh_secs}s")
    else:
        auto_refresh = False

    # ── Load data ─────────────────────────────────────────────
    cache_key = f"intraday_data_{ticker}_{selected_tf}"

    if refresh or cache_key not in st.session_state:
        with st.spinner(f"Loading {selected_tf} data for {ticker}…"):
            result = get_intraday_data(ticker, selected_tf, force_refresh=refresh)
            st.session_state[cache_key] = result
            st.session_state[f"intraday_load_time_{cache_key}"] = time.time()

    result = st.session_state.get(cache_key, {})

    # Auto-refresh check
    if auto_refresh and is_fast:
        load_time   = st.session_state.get(f"intraday_load_time_{cache_key}", 0)
        refresh_secs= {"1m": 30, "5m": 60}.get(selected_tf, 60)
        if time.time() - load_time > refresh_secs:
            result = get_intraday_data(ticker, selected_tf, force_refresh=True)
            st.session_state[cache_key] = result
            st.session_state[f"intraday_load_time_{cache_key}"] = time.time()
            st.rerun()

    # ── Error handling ────────────────────────────────────────
    if result.get("error") or result.get("df") is None:
        st.error(result.get("error", "No data returned."))
        _render_no_data_help(selected_tf)
        return

    df     = result["df"]
    source = result.get("source", "unknown")

    # ── Summary metrics ───────────────────────────────────────
    _render_price_summary(df, ticker, selected_tf, source)

    # ── Chart ─────────────────────────────────────────────────
    fig = _build_chart(
        df, ticker, selected_tf, source,
        show_ema=show_ema,
        show_vwap=show_vwap,
        show_bb=show_bb,
        show_rsi=show_rsi,
        show_macd=show_macd,
    )
    st.plotly_chart(fig, use_container_width=True, config={
        "displayModeBar": True,
        "modeBarButtonsToAdd": ["drawline", "drawopenpath", "eraseshape"],
        "scrollZoom": True,
    })

    # ── Export ────────────────────────────────────────────────
    col_dl, col_info = st.columns([1, 4])
    with col_dl:
        csv = df.to_csv(index=False)
        st.download_button(
            "⬇️ CSV",
            data=csv,
            file_name=f"{ticker}_{selected_tf}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            key="intraday_csv",
        )
    with col_info:
        st.caption(
            f"{len(df):,} bars · "
            f"{df['Date'].min().strftime('%Y-%m-%d %H:%M')} → "
            f"{df['Date'].max().strftime('%Y-%m-%d %H:%M')} UTC · "
            f"Source: {source}"
        )


def _render_price_summary(df: pd.DataFrame, ticker: str,
                          interval: str, source: str):
    """Compact price metrics row above the chart."""
    last    = float(df["Close"].iloc[-1])
    prev    = float(df["Close"].iloc[-2]) if len(df) > 1 else last
    chg     = last - prev
    chg_pct = chg / prev * 100 if prev else 0
    high    = float(df["High"].max())
    low     = float(df["Low"].min())
    vol     = float(df["Volume"].sum())
    avg_vol = float(df["Volume"].mean())
    last_vol= float(df["Volume"].iloc[-1])

    delta_color = "normal" if chg >= 0 else "inverse"
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Last",    f"${last:,.2f}",
              f"{chg:+.2f} ({chg_pct:+.2f}%)", delta_color=delta_color)
    c2.metric(f"Period High", f"${high:,.2f}")
    c3.metric(f"Period Low",  f"${low:,.2f}")
    c4.metric("Total Volume", f"{vol/1e6:.1f}M" if vol >= 1e6 else f"{vol/1e3:.0f}K")
    c5.metric("Avg Bar Vol",  f"{avg_vol:,.0f}")
    c6.metric("Bars",         f"{len(df):,}",
              delta=TIMEFRAMES[interval]["label"], delta_color="off")


def _render_no_data_help(interval: str):
    """Show helpful info when no data is available."""
    is_intraday = interval not in ("1d", "1w")
    if is_intraday:
        st.info(
            "**Intraday data availability:**\n\n"
            "- **MarketData.app** — intraday candles on paid plans\n"
            "- **Polygon** — intraday requires Stocks Starter ($29/mo)\n"
            "- **Alpaca** — free tier supports 15-min delayed data (add `ALPACA_API_KEY` + `ALPACA_API_SECRET` to secrets)\n\n"
            "Your current keys return daily bars only. "
            "Alpaca has a free account tier that includes intraday data — "
            "register at [alpaca.markets](https://alpaca.markets) and add the keys to secrets."
        )
    else:
        st.info("Daily/weekly data should be available. Check that your API keys are valid.")


# ─────────────────────────────────────────────────────────────
# Embeddable widget for Stock Dashboard
# ─────────────────────────────────────────────────────────────

def render_intraday_chart(db, user: dict, ticker: str,
                          default_interval: str = "15m",
                          height: int = 400):
    """
    Compact intraday chart widget for embedding in Stock Dashboard.
    Shows a timeframe picker and chart without all the full-page controls.
    """
    if not PLOTLY_AVAILABLE:
        st.caption("Install plotly for intraday charts: `pip install plotly`")
        return

    intervals = ["1m", "5m", "15m", "1h", "1d"]
    sel = st.radio(
        "Timeframe",
        intervals,
        index=intervals.index(default_interval) if default_interval in intervals else 2,
        horizontal=True,
        key=f"intraday_widget_{ticker}",
    )

    cache_key = f"intraday_widget_data_{ticker}_{sel}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading {sel} chart…"):
            st.session_state[cache_key] = get_intraday_data(ticker, sel)

    result = st.session_state[cache_key]

    if result.get("error") or result.get("df") is None:
        st.caption(f"No {sel} data available. " + result.get("error", ""))
        return

    df     = result["df"]
    source = result.get("source", "")

    # Minimal chart for embedded view
    fig = _build_chart(
        df, ticker, sel, source,
        show_ema=True, show_vwap=(sel not in ("1d","1w")),
        show_bb=False, show_rsi=False, show_macd=False,
    )
    fig.update_layout(height=height, margin=dict(l=0, r=30, t=20, b=10))
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": False, "scrollZoom": True})