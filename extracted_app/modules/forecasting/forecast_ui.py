"""
modules/forecasting/forecast_ui.py

Streamlit UI for the three new Market Terminal features:
  1. AI Price Forecast  — extends the price chart with projected path
  2. Congress Trades    — disclosures by members of Congress
  3. Institutional Flow — 13F filing ownership and top movers

How to add to your app.py:
─────────────────────────────────────────────────────────────
Add "AI Forecast" to the `pages` list in section 15, then:

    elif page == "AI Forecast":
        from modules.forecasting.forecast_ui import render_forecast_page
        render_forecast_page(db, user)
─────────────────────────────────────────────────────────────

You can also embed render_forecast_panel() inside the existing
Stock Dashboard page by calling it from stock_dashboard_ui.py:

    from modules.forecasting.forecast_ui import render_forecast_panel
    render_forecast_panel(db, user, symbol)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st

from modules.market_data.service import get_price_history
from modules.forecasting.forecast_engine import (
    generate_ai_forecast,
    anthropic_enabled,
)
from modules.forecasting.congress_service import get_congress_trades
from modules.forecasting.institutional_service import get_institutional_flow


# ═══════════════════════════════════════════════════════════════
# TOP-LEVEL PAGE  (add as a sidebar page in app.py)
# ═══════════════════════════════════════════════════════════════

def render_forecast_page(db, user):
    st.header("📈 AI Forecast & Market Intelligence")

    col_ticker, col_period, _ = st.columns([1, 1, 4])
    with col_ticker:
        symbol = st.text_input(
            "Ticker", value="NVDA", key="forecast_ticker"
        ).upper().strip()
    with col_period:
        period = st.selectbox(
            "History", ["3mo", "6mo", "1y", "2y"],
            index=2, key="forecast_period"
        )

    if not symbol:
        st.info("Enter a ticker symbol to begin.")
        return

    tab_forecast, tab_congress, tab_inst = st.tabs([
        "🤖 AI Price Forecast",
        "🏛️ Congress Trades",
        "🏦 Institutional Flow",
    ])

    with tab_forecast:
        render_forecast_panel(db, user, symbol, period)

    with tab_congress:
        render_congress_panel(symbol)

    with tab_inst:
        render_institutional_panel(symbol)


# ═══════════════════════════════════════════════════════════════
# PANEL 1 — AI Price Forecast
# ═══════════════════════════════════════════════════════════════

def render_forecast_panel(db, user, symbol: str, period: str = "1y"):
    """
    Can be called standalone (full page) or embedded inside Stock Dashboard.
    Renders the price chart + AI forecast overlay.
    """
    st.subheader(f"AI Price Forecast — {symbol}")

    if not anthropic_enabled():
        st.warning(
            "⚠️ ANTHROPIC_API_KEY is not set. "
            "Forecast will use a statistical fallback. "
            "Set the key in your environment or Streamlit secrets to enable full AI forecasts."
        )

    # ── Load price history ────────────────────────────────────
    with st.spinner("Loading price history…"):
        try:
            px = get_price_history(db, symbol, period=period, interval="1d")
        except Exception as e:
            st.error(f"Failed to load price history: {e}")
            return

    if px is None or px.empty:
        st.warning(f"No price data available for {symbol}.")
        return

    # Normalise columns
    px = px.copy()
    if "close" in px.columns and "Close" not in px.columns:
        px = px.rename(columns={"close": "Close"})
    if "date" in px.columns and "Date" not in px.columns:
        px = px.rename(columns={"date": "Date"})

    px = px.dropna(subset=["Close"])
    if px.empty:
        st.warning("Price data has no valid Close values.")
        return

    # ── Forecast button ───────────────────────────────────────
    horizon = st.select_slider(
        "Forecast horizon (trading days)",
        options=[7, 14, 21, 30],
        value=30,
        key=f"forecast_horizon_{symbol}",
    )

    cache_key = f"forecast_{symbol}_{period}_{horizon}"

    col_btn, col_clear, _ = st.columns([1, 1, 4])
    with col_btn:
        run_btn = st.button(
            "🤖 Generate AI Forecast",
            key=f"run_forecast_{symbol}",
            type="primary",
        )
    with col_clear:
        if st.button("✕ Clear forecast", key=f"clear_forecast_{symbol}"):
            if cache_key in st.session_state:
                del st.session_state[cache_key]
            st.rerun()

    if run_btn:
        with st.spinner("Generating AI forecast… this takes ~5 seconds"):
            # Pass analytics snapshot context if available
            extra = _get_snapshot_context(db, user, symbol)
            fc = generate_ai_forecast(symbol, px, horizon_days=horizon, extra_context=extra)
            st.session_state[cache_key] = fc

    fc = st.session_state.get(cache_key)

    # ── Chart ──────────────────────────────────────────────────
    _render_forecast_chart(px, symbol, fc)

    # ── Forecast summary cards ────────────────────────────────
    if fc and not fc.get("error") or (fc and fc.get("mid_prices")):
        _render_forecast_cards(fc, symbol)


def _render_forecast_chart(px: pd.DataFrame, symbol: str, fc: dict | None):
    """
    Renders the historical price chart.  If `fc` is provided, extends
    the x-axis to the right with the AI projected path and confidence band.
    """
    fig, ax = plt.subplots(figsize=(12, 4))

    # ── Historical line ────────────────────────────────────────
    if "Date" in px.columns:
        dates = pd.to_datetime(px["Date"])
    else:
        dates = px.index

    closes = pd.to_numeric(px["Close"], errors="coerce")
    ax.plot(dates, closes, color="#1D9E75", linewidth=1.8, label="Historical price")
    ax.fill_between(dates, closes, closes.min() * 0.95, alpha=0.06, color="#1D9E75")

    # ── Divider between history and forecast ──────────────────
    last_hist_date = dates.iloc[-1]
    last_price     = float(closes.iloc[-1])

    if fc and fc.get("mid_prices"):
        forecast_dates = pd.to_datetime(fc["forecast_dates"])
        mid   = fc["mid_prices"]
        bull  = fc["bull_prices"]
        bear  = fc["bear_prices"]

        # Join historical and forecast with a single connector point
        all_fc_dates  = [last_hist_date] + list(forecast_dates)
        all_mid        = [last_price]   + mid
        all_bull       = [last_price]   + bull
        all_bear_       = [last_price]  + bear

        # Confidence band (fill between bear and bull)
        ax.fill_between(
            all_fc_dates, all_bear_, all_bull,
            color="#378ADD", alpha=0.12, label="Confidence band"
        )
        # Bear / bull boundary lines
        ax.plot(all_fc_dates, all_bull,  color="#1D9E75", linewidth=0.8,
                linestyle="--", alpha=0.6)
        ax.plot(all_fc_dates, all_bear_, color="#E24B4A", linewidth=0.8,
                linestyle="--", alpha=0.6)
        # Central forecast path
        ax.plot(
            all_fc_dates, all_mid,
            color="#378ADD", linewidth=2.0, linestyle="--",
            label="AI forecast (central path)", zorder=5
        )

        # Vertical divider
        ax.axvline(last_hist_date, color="#888888", linewidth=0.8,
                   linestyle=":", alpha=0.7)
        ax.text(
            last_hist_date, ax.get_ylim()[0],
            "  Today", fontsize=8, color="#888888", va="bottom"
        )

    ax.set_title(f"{symbol} — Price Chart {'+ AI Forecast' if fc else ''}", fontsize=13)
    ax.set_xlabel("Date", fontsize=10)
    ax.set_ylabel("Price (USD)", fontsize=10)
    ax.grid(True, alpha=0.2)
    ax.legend(loc="upper left", fontsize=9)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _render_forecast_cards(fc: dict, symbol: str):
    last = fc.get("last_price") or 0.0
    t7   = fc.get("target_7d")
    t30  = fc.get("target_30d")
    conf = fc.get("confidence_pct", 0)
    sig  = fc.get("signal", "Neutral")
    strength = fc.get("signal_strength", "")
    rationale = fc.get("rationale", "")

    def pct_str(target):
        if not target or not last:
            return ""
        p = ((target - last) / last) * 100
        arrow = "▲" if p >= 0 else "▼"
        return f"{arrow} {abs(p):.1f}%"

    def delta_color(target):
        if not target or not last:
            return None
        return "normal" if target >= last else "inverse"

    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "7-Day Target",
        f"${t7:.2f}" if t7 else "N/A",
        delta=pct_str(t7),
        delta_color=delta_color(t7) or "normal",
    )
    c2.metric(
        "30-Day Target",
        f"${t30:.2f}" if t30 else "N/A",
        delta=pct_str(t30),
        delta_color=delta_color(t30) or "normal",
    )

    sig_color = {"Bullish": "🟢", "Bearish": "🔴", "Neutral": "🟡"}.get(sig, "⚪")
    c3.metric("Signal", f"{sig_color} {sig}", delta=strength, delta_color="off")
    c4.metric("Confidence", f"{conf}%")

    if rationale:
        st.info(f"**AI Analysis:** {rationale}")

    if fc.get("error"):
        st.caption(f"⚠️ Note: {fc['error']}")


# ═══════════════════════════════════════════════════════════════
# PANEL 2 — Congress Trades
# ═══════════════════════════════════════════════════════════════

def render_congress_panel(symbol: str):
    st.subheader(f"🏛️ Congressional Trading — {symbol}")
    st.caption(
        "Disclosures filed under the STOCK Act (45-day reporting window). "
        "Data sourced from House Stock Watcher / Quiver Quant."
    )

    days_back = st.select_slider(
        "Lookback window", options=[30, 60, 90, 180, 365],
        value=180, key=f"cong_days_{symbol}"
    )

    cache_key = f"congress_{symbol}_{days_back}"

    if cache_key not in st.session_state:
        with st.spinner("Fetching congressional disclosures…"):
            trades = get_congress_trades(symbol, days_back=days_back)
            st.session_state[cache_key] = trades

    trades = st.session_state[cache_key]

    if not trades:
        st.info(
            f"No congressional trades found for {symbol} in the last {days_back} days. "
            "This may mean no disclosures were filed, or the data source is unavailable. "
            "Try setting QUIVER_API_KEY for more complete data."
        )
        return

    # ── Summary metrics ───────────────────────────────────────
    buys  = [t for t in trades if t["trade_type"] == "buy"]
    sells = [t for t in trades if t["trade_type"] == "sell"]
    net_label = "🟢 Bullish" if len(buys) > len(sells) else "🔴 Bearish" if len(sells) > len(buys) else "🟡 Neutral"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Disclosures", len(trades))
    c2.metric("Buys", len(buys))
    c3.metric("Sells", len(sells))
    c4.metric("Congress Bias", net_label)

    # ── Filter ────────────────────────────────────────────────
    filter_type = st.radio(
        "Show", ["All", "Buys only", "Sells only"],
        horizontal=True, key=f"cong_filter_{symbol}"
    )
    if filter_type == "Buys only":
        trades = buys
    elif filter_type == "Sells only":
        trades = sells

    # ── Table ─────────────────────────────────────────────────
    rows = []
    for t in trades:
        trade_emoji = "🟢 BUY" if t["trade_type"] == "buy" else "🔴 SELL" if t["trade_type"] == "sell" else "🔄 EXCHANGE"
        delay = f"{t['delay_days']}d" if t.get("delay_days") is not None else "—"
        rows.append({
            "Member":       t["member"],
            "Party":        t.get("party") or "—",
            "Chamber":      t.get("chamber") or "—",
            "Trade":        trade_emoji,
            "Amount":       t["amount_range"],
            "Trade Date":   t["trade_date"] or "Unknown",
            "Disclosed":    t["disclosure_date"] or "—",
            "Delay":        delay,
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Buy/Sell timeline mini-chart ──────────────────────────
    if len(trades) >= 3:
        _render_congress_chart(trades, symbol)


def _render_congress_chart(trades: list, symbol: str):
    """Simple bar chart showing buy/sell volume by month."""
    try:
        df = pd.DataFrame(trades)
        df["trade_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
        df = df.dropna(subset=["trade_date"])
        df["month"] = df["trade_date"].dt.to_period("M").astype(str)

        buys  = df[df["trade_type"] == "buy"].groupby("month").size()
        sells = df[df["trade_type"] == "sell"].groupby("month").size()

        months = sorted(set(list(buys.index) + list(sells.index)))
        buy_vals  = [buys.get(m, 0)  for m in months]
        sell_vals = [sells.get(m, 0) for m in months]

        x = range(len(months))
        fig, ax = plt.subplots(figsize=(10, 2.5))
        ax.bar(x, buy_vals,  color="#1D9E75", alpha=0.8, label="Buys",  width=0.4, align="edge")
        ax.bar([i + 0.4 for i in x], sell_vals, color="#E24B4A", alpha=0.8, label="Sells", width=0.4, align="edge")
        ax.set_xticks([i + 0.4 for i in x])
        ax.set_xticklabels(months, rotation=45, fontsize=8)
        ax.set_title(f"Congress Buy/Sell Activity — {symbol}", fontsize=11)
        ax.legend(fontsize=9)
        ax.grid(axis="y", alpha=0.2)
        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    except Exception:
        pass  # Chart is bonus — don't break the page


# ═══════════════════════════════════════════════════════════════
# PANEL 3 — Institutional Flow
# ═══════════════════════════════════════════════════════════════

def render_institutional_panel(symbol: str):
    st.subheader(f"🏦 Institutional Flow — {symbol}")
    st.caption("Based on SEC 13F filings. Updated quarterly.")

    cache_key = f"inst_flow_{symbol}"

    if cache_key not in st.session_state:
        with st.spinner("Loading institutional ownership data…"):
            data = get_institutional_flow(symbol)
            st.session_state[cache_key] = data

    data = st.session_state[cache_key]

    # ── Summary metrics ───────────────────────────────────────
    own_pct   = data.get("ownership_pct")
    net_chg   = data.get("net_change_shares")
    num_hold  = data.get("num_holders")
    as_of     = data.get("as_of", "")

    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Institutional Ownership",
        f"{own_pct:.1f}%" if own_pct is not None else "N/A",
    )

    if net_chg is not None:
        net_label = f"+{net_chg:,.0f}" if net_chg >= 0 else f"{net_chg:,.0f}"
        c2.metric("Net Shares (last quarter)", net_label,
                  delta="Net buy" if net_chg >= 0 else "Net sell",
                  delta_color="normal" if net_chg >= 0 else "inverse")
    else:
        c2.metric("Net Shares (last quarter)", "N/A")

    c3.metric("Institutions Holding", f"{num_hold:,}" if num_hold else "N/A")

    st.caption(f"Source: {data.get('source', 'Unknown')} · As of: {as_of}")

    # ── Top holders table + bar chart ─────────────────────────
    holders = data.get("top_holders", [])

    if not holders:
        st.info(
            "No institutional holder data available. "
            "yfinance is used as the default source — ensure it is installed. "
            "For richer 13F data, set FINTEL_API_KEY."
        )
        return

    st.markdown("#### Top institutional holders — last 13F filing")

    col_filter = st.radio(
        "Filter", ["All", "Increasing position", "Decreasing position"],
        horizontal=True, key=f"inst_filter_{symbol}"
    )
    filtered = holders
    if col_filter == "Increasing position":
        filtered = [h for h in holders if h["direction"] == "inc"]
    elif col_filter == "Decreasing position":
        filtered = [h for h in holders if h["direction"] == "dec"]

    rows = []
    for h in filtered:
        direction_label = "📈 Increasing" if h["direction"] == "inc" else "📉 Decreasing"
        chg_str = f"+{h['pct_change']:.1f}%" if h["pct_change"] >= 0 else f"{h['pct_change']:.1f}%"
        rows.append({
            "Institution":  h["name"],
            "Shares Held":  f"{h['shares_held']:,}",
            "QoQ Change":   chg_str,
            "Direction":    direction_label,
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Horizontal bar chart ───────────────────────────────────
    _render_institutional_chart(filtered, symbol)


def _render_institutional_chart(holders: list, symbol: str):
    if not holders:
        return
    try:
        names  = [h["name"][:28] for h in holders]
        values = [abs(h["pct_change"]) for h in holders]
        colors = ["#1D9E75" if h["direction"] == "inc" else "#E24B4A" for h in holders]

        fig, ax = plt.subplots(figsize=(10, max(2.5, len(holders) * 0.45)))
        y_pos = range(len(names))
        ax.barh(y_pos, values, color=colors, alpha=0.8, height=0.6)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(names, fontsize=9)
        ax.set_xlabel("QoQ % Change (absolute)", fontsize=9)
        ax.set_title(f"Institutional Position Changes — {symbol}", fontsize=11)
        ax.grid(axis="x", alpha=0.2)

        green_patch = mpatches.Patch(color="#1D9E75", label="Increasing")
        red_patch   = mpatches.Patch(color="#E24B4A", label="Decreasing")
        ax.legend(handles=[green_patch, red_patch], fontsize=9, loc="lower right")

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════
# Helper — pull analytics snapshot context for richer forecasts
# ═══════════════════════════════════════════════════════════════

def _get_snapshot_context(db, user, symbol: str) -> dict | None:
    try:
        from modules.analytics.models import AnalyticsSnapshot

        snap = (
            db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.tenant_id == user["tenant_id"],
                AnalyticsSnapshot.symbol == symbol,
            )
            .order_by(AnalyticsSnapshot.asof.desc())
            .first()
        )
        if not snap:
            return None

        return {
            "composite_score": getattr(snap, "composite_score", None),
            "confidence_score": getattr(snap, "confidence_score", None),
            "momentum":         getattr(snap, "momentum", None),
            "quality":          getattr(snap, "quality", None),
            "growth":           getattr(snap, "growth", None),
            "value":            getattr(snap, "value", None),
            "risk":             getattr(snap, "risk", None),
            "sector":           getattr(snap, "sector", None),
            "rating":           getattr(snap, "rating", None),
        }
    except Exception:
        return None
