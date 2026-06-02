"""
modules/options_flow/flow_ui.py

Options Flow & Dark Pool Intelligence — Streamlit UI.

Four tabs:
  🌊 Live Flow    — unusual options activity, sweeps, blocks
  🌑 Dark Pool    — off-exchange block prints with key levels
  📊 Sentiment    — put/call ratio, premium split, net flow
  🏦 Insider Flow — SEC Form 4 insider transactions

Add to app.py:
    pages list: "Options Flow"
    elif page == "Options Flow":
        from modules.options_flow.flow_ui import render_options_flow_page
        render_options_flow_page(db, user)

Requires: UNUSUAL_WHALES_API_KEY in secrets.toml
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import streamlit as st

from modules.options_flow.flow_service import (
    api_available,
    get_darkpool_flow,
    get_greek_exposure,
    get_insider_flow,
    get_options_flow,
    get_options_sentiment,
    get_market_flow_summary,
)


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_options_flow_page(db, user: dict):
    st.header("🌊 Options Flow & Dark Pool Intelligence")
    st.caption(
        "Institutional smart money tracking · Unusual options activity · "
        "Dark pool prints · Insider transactions · Powered by Unusual Whales"
    )

    if not api_available():
        st.warning(
            "⚠️ **UNUSUAL_WHALES_API_KEY not set.** "
            "Add it to your Streamlit secrets to enable live options flow data. "
            "Get an API key at [unusualwhales.com/pricing](https://unusualwhales.com/pricing?product=api)"
        )
        _render_demo_mode()
        return

    # ── Symbol input ──────────────────────────────────────────
    col_sym, col_premium, col_refresh = st.columns([1, 1, 1])
    with col_sym:
        ticker = st.text_input(
            "Symbol (optional — leave blank for market-wide)",
            placeholder="NVDA",
            key="flow_ticker",
        ).upper().strip()
    with col_premium:
        min_premium = st.selectbox(
            "Min premium ($)",
            [10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000],
            index=2,
            format_func=lambda x: f"${x:,.0f}",
            key="flow_min_prem",
        )
    with col_refresh:
        st.write("")
        refresh = st.button("↺ Refresh", key="flow_refresh", use_container_width=True)

    if refresh:
        keys = [k for k in st.session_state if k.startswith("flow_data_")]
        for k in keys:
            del st.session_state[k]

    tab_flow, tab_dark, tab_sentiment, tab_insider = st.tabs([
        "🌊 Live Options Flow",
        "🌑 Dark Pool Prints",
        "📊 Flow Sentiment",
        "🏦 Insider Transactions",
    ])

    with tab_flow:
        _render_flow_tab(ticker, min_premium)

    with tab_dark:
        _render_darkpool_tab(ticker)

    with tab_sentiment:
        _render_sentiment_tab(ticker)

    with tab_insider:
        _render_insider_tab(ticker)


# ─────────────────────────────────────────────────────────────
# Tab 1 — Live Options Flow
# ─────────────────────────────────────────────────────────────

def _render_flow_tab(ticker: str, min_premium: int):
    st.subheader(
        f"Unusual Options Activity — "
        f"{'Market-Wide' if not ticker else ticker}",
    )
    st.caption(
        "Large premium trades, sweeps (aggressive multi-exchange fills), "
        "and block orders that signal institutional conviction."
    )

    cache_key = f"flow_data_options_{ticker}_{min_premium}"
    if cache_key not in st.session_state:
        with st.spinner("Fetching options flow…"):
            flow = get_options_flow(ticker or None, min_premium=min_premium, limit=100)
            st.session_state[cache_key] = flow

    flow = st.session_state.get(cache_key, [])

    if not flow:
        st.info(
            "No unusual flow found above that premium threshold. "
            "Try lowering the minimum premium or changing the symbol."
        )
        return

    # Summary metrics
    calls = [f for f in flow if f["type"] == "CALL"]
    puts  = [f for f in flow if f["type"] == "PUT"]
    sweeps= [f for f in flow if f["is_sweep"]]
    blocks= [f for f in flow if f["is_block"]]
    total_prem = sum(f["premium"] for f in flow)
    call_prem  = sum(f["premium"] for f in calls)
    put_prem   = sum(f["premium"] for f in puts)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Trades",   len(flow))
    c2.metric("Total Premium",  f"${total_prem/1e6:.1f}M")
    c3.metric("Calls / Puts",   f"{len(calls)} / {len(puts)}")
    c4.metric("Sweeps",         len(sweeps),
              help="Aggressive fills across multiple exchanges simultaneously")
    c5.metric("Blocks",         len(blocks),
              help="Single large orders, often negotiated off-exchange")

    # Sentiment bar
    if total_prem > 0:
        call_pct = call_prem / total_prem * 100
        put_pct  = 100 - call_pct
        bull_color = "#1D9E75" if call_pct > 50 else "#E24B4A"
        st.markdown(
            f"**Premium sentiment:** "
            f"<span style='color:#1D9E75'>Calls {call_pct:.0f}%</span> / "
            f"<span style='color:#E24B4A'>Puts {put_pct:.0f}%</span>",
            unsafe_allow_html=True,
        )

    # Filters
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        type_filter = st.radio(
            "Type", ["All", "Calls Only", "Puts Only"],
            horizontal=True, key="flow_type_filter"
        )
    with col_f2:
        trade_filter = st.radio(
            "Trade type", ["All", "Sweeps", "Blocks"],
            horizontal=True, key="flow_trade_filter"
        )

    filtered = flow
    if type_filter == "Calls Only":
        filtered = [f for f in filtered if f["type"] == "CALL"]
    elif type_filter == "Puts Only":
        filtered = [f for f in filtered if f["type"] == "PUT"]
    if trade_filter == "Sweeps":
        filtered = [f for f in filtered if f["is_sweep"]]
    elif trade_filter == "Blocks":
        filtered = [f for f in filtered if f["is_block"]]

    if not filtered:
        st.info("No trades match the current filter.")
        return

    # Table
    rows = []
    for f in filtered[:100]:
        type_emoji  = "🟢 CALL" if f["type"] == "CALL" else "🔴 PUT"
        flags = []
        if f["is_sweep"]: flags.append("⚡ SWEEP")
        if f["is_block"]: flags.append("🧱 BLOCK")
        flag_str = " ".join(flags) or "—"

        otm_pct = None
        if f["underlying_price"] and f["strike"]:
            if f["type"] == "CALL":
                otm_pct = (f["strike"] - f["underlying_price"]) / f["underlying_price"] * 100
            else:
                otm_pct = (f["underlying_price"] - f["strike"]) / f["underlying_price"] * 100

        rows.append({
            "Ticker":     f["ticker"] or ticker,
            "Type":       type_emoji,
            "Strike":     f"${f['strike']:,.0f}" if f["strike"] else "—",
            "Expiry":     f["expiry"],
            "Premium":    f"${f['premium']:,.0f}",
            "Size":       f"{f['size']:,}",
            "OI":         f"{f['open_interest']:,}" if f["open_interest"] else "—",
            "OTM%":       f"{otm_pct:+.1f}%" if otm_pct is not None else "—",
            "Side":       f["side"],
            "Flags":      flag_str,
            "Spot":       f"${f['underlying_price']:,.2f}" if f["underlying_price"] else "—",
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    csv = pd.DataFrame(rows).to_csv(index=False)
    st.download_button(
        "⬇️ Export CSV",
        data=csv,
        file_name=f"options_flow_{ticker or 'market'}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        key="flow_export",
    )

    # Premium over time chart
    _render_premium_chart(filtered)


def _render_premium_chart(flow: list):
    """Bar chart of premium by ticker (market-wide) or strike (single ticker)."""
    if not flow or len(flow) < 3:
        return

    # Group by ticker or by type
    by_ticker: dict = {}
    for f in flow:
        k = f["ticker"] or "UNKNOWN"
        by_ticker[k] = by_ticker.get(k, 0) + f["premium"]

    if len(by_ticker) == 1:
        # Single ticker — show by strike
        by_strike: dict = {}
        for f in flow:
            k = f["strike"]
            if k:
                by_strike[k] = by_strike.get(k, 0) + f["premium"]
        if not by_strike:
            return
        labels = [f"${k:,.0f}" for k in sorted(by_strike.keys())]
        values = [by_strike[k] for k in sorted(by_strike.keys())]
        title  = "Premium by Strike"
    else:
        sorted_items = sorted(by_ticker.items(), key=lambda x: x[1], reverse=True)[:15]
        labels = [x[0] for x in sorted_items]
        values = [x[1] for x in sorted_items]
        title  = "Top Premium by Ticker"

    colors = ["#1D9E75" if v > 0 else "#E24B4A" for v in values]

    fig, ax = plt.subplots(figsize=(10, 3), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    ax.bar(range(len(labels)), [v/1e3 for v in values], color=colors, alpha=0.85)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8, color="#8B949E")
    ax.set_ylabel("Premium ($K)", color="#8B949E", fontsize=8)
    ax.set_title(title, color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.4, alpha=0.6)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Tab 2 — Dark Pool
# ─────────────────────────────────────────────────────────────

def _render_darkpool_tab(ticker: str):
    st.subheader(
        f"Dark Pool Prints — "
        f"{'Market-Wide' if not ticker else ticker}"
    )
    st.caption(
        "Off-exchange block trades routed through private dark pools. "
        "Large prints at key price levels often act as support/resistance. "
        "High dark pool volume relative to lit exchange = institutional accumulation."
    )

    cache_key = f"flow_data_dark_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner("Fetching dark pool data…"):
            dp = get_darkpool_flow(ticker or None, min_size=5000, limit=100)
            st.session_state[cache_key] = dp

    dp = st.session_state.get(cache_key, [])

    if not dp:
        st.info("No dark pool prints found. Try a different symbol or lower the minimum size.")
        return

    # Summary
    total_notional = sum(f["notional"] for f in dp)
    avg_size       = sum(f["size"] for f in dp) / len(dp)
    biggest        = dp[0] if dp else {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Prints",     len(dp))
    c2.metric("Total Notional",   f"${total_notional/1e6:.1f}M")
    c3.metric("Avg Size",         f"{avg_size:,.0f} shares")
    c4.metric("Largest Print",    f"${biggest.get('notional', 0)/1e6:.1f}M" if biggest else "—")

    # Table
    rows = []
    for f in dp[:100]:
        sent_emoji = {"bullish": "🟢", "bearish": "🔴"}.get(f["sentiment"], "⚪")
        rows.append({
            "Ticker":   f["ticker"] or ticker,
            "Price":    f"${f['price']:,.2f}" if f["price"] else "—",
            "Size":     f"{f['size']:,}",
            "Notional": f"${f['notional']:,.0f}",
            "Sentiment":f"{sent_emoji} {f['sentiment'].title()}" if f["sentiment"] else "—",
            "Time":     f["timestamp"][:16] if f["timestamp"] else "—",
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )

    # Price level heatmap for single ticker
    if ticker and dp:
        _render_darkpool_levels(dp, ticker)


def _render_darkpool_levels(dp: list, ticker: str):
    """Show dark pool prints as price level clusters."""
    prices     = [f["price"] for f in dp if f.get("price")]
    notionals  = [f["notional"] for f in dp if f.get("price")]

    if not prices or len(prices) < 2:
        return

    st.markdown("#### 🎯 Dark Pool Price Level Clusters")
    st.caption(
        "Larger bubbles = higher notional volume at that price. "
        "Clusters act as institutional support/resistance."
    )

    fig, ax = plt.subplots(figsize=(10, 3), facecolor="#0F1117")
    ax.set_facecolor("#161B22")

    sizes  = [max(20, n / max(notionals) * 800) for n in notionals]
    colors = ["#378ADD"] * len(prices)

    ax.scatter(prices, [1] * len(prices), s=sizes, c=colors, alpha=0.6)

    for price, size in zip(prices, sizes):
        if size > 200:
            ax.axvline(price, color="#378ADD", linewidth=0.5, alpha=0.3)

    ax.set_xlabel("Price ($)", color="#8B949E", fontsize=9)
    ax.set_yticks([])
    ax.set_title(
        f"{ticker} Dark Pool Levels — size = notional volume",
        color="#C9D1D9", fontsize=10
    )
    ax.spines[:].set_color("#21262D")
    ax.tick_params(colors="#8B949E")
    ax.grid(axis="x", color="#21262D", linewidth=0.4, alpha=0.4)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Tab 3 — Sentiment
# ─────────────────────────────────────────────────────────────

def _render_sentiment_tab(ticker: str):
    st.subheader("Options Flow Sentiment")

    if not ticker:
        st.info("Enter a ticker symbol above to see put/call ratio and flow sentiment.")
        return

    cache_key = f"flow_data_sentiment_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading sentiment for {ticker}…"):
            sent = get_options_sentiment(ticker)
            gex  = get_greek_exposure(ticker)
            st.session_state[cache_key] = {"sentiment": sent, "gex": gex}

    data = st.session_state.get(cache_key, {})
    sent = data.get("sentiment", {})
    gex  = data.get("gex", {})

    if not sent:
        st.info(f"No options sentiment data available for {ticker}.")
        return

    call_vol  = sent.get("call_volume", 0)
    put_vol   = sent.get("put_volume", 0)
    call_prem = sent.get("call_premium", 0) or 0
    put_prem  = sent.get("put_premium", 0) or 0
    pc_ratio  = sent.get("put_call_ratio")
    net_sent  = sent.get("net_sentiment", "")

    # P/C ratio interpretation
    if pc_ratio is not None:
        if pc_ratio < 0.7:
            pc_label = "🟢 Bullish (low put activity)"
        elif pc_ratio > 1.2:
            pc_label = "🔴 Bearish (high put activity)"
        else:
            pc_label = "🟡 Neutral"
    else:
        pc_label = "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Call Volume",    f"{call_vol:,}")
    c2.metric("Put Volume",     f"{put_vol:,}")
    c3.metric("P/C Ratio",
              f"{pc_ratio:.2f}" if pc_ratio else "—",
              delta=pc_label, delta_color="off")
    c4.metric("Net Sentiment",  net_sent.title() if net_sent else "—")

    if call_prem or put_prem:
        total = call_prem + put_prem
        call_pct = call_prem / total * 100 if total else 50
        put_pct  = 100 - call_pct

        # Donut
        fig, ax = plt.subplots(figsize=(4, 4), facecolor="#0F1117")
        ax.set_facecolor("#0F1117")
        wedges, _, autotexts = ax.pie(
            [call_pct, put_pct],
            labels=None,
            autopct="%1.0f%%",
            colors=["#1D9E75", "#E24B4A"],
            startangle=90,
            wedgeprops={"linewidth": 2, "edgecolor": "#0F1117"},
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontsize(11)
        centre = plt.Circle((0, 0), 0.55, fc="#0F1117")
        ax.add_artist(centre)
        sentiment_label = "Bullish" if call_pct > 55 else "Bearish" if put_pct > 55 else "Mixed"
        ax.text(0, 0, sentiment_label, ha="center", va="center",
                fontsize=12, color="white", fontweight="bold")
        ax.legend(
            ["Calls", "Puts"],
            loc="lower center",
            fontsize=9,
            facecolor="#0F1117",
            labelcolor="white",
            framealpha=0.3,
        )
        ax.set_title(f"{ticker} Premium Split", color="white", fontsize=11)
        plt.tight_layout()
        col_chart, col_gex = st.columns(2)
        with col_chart:
            st.pyplot(fig)
        plt.close(fig)

        with col_gex:
            if gex:
                st.markdown("#### ⚡ Greek Exposure (GEX)")
                st.metric("Total Gamma",  f"{gex.get('gamma', 0):+,.2f}" if gex.get("gamma") else "—")
                st.metric("Total Delta",  f"{gex.get('delta', 0):+,.2f}" if gex.get("delta") else "—")
                if gex.get("gex_flip_level"):
                    st.metric(
                        "GEX Flip Level",
                        f"${gex['gex_flip_level']:,.2f}",
                        help="Price where gamma flips from positive to negative — key level for vol"
                    )
                st.caption(
                    "GEX Flip Level = price where market makers shift from stabilising "
                    "to amplifying moves. Break above = acceleration, break below = volatility."
                )


# ─────────────────────────────────────────────────────────────
# Tab 4 — Insider Flow
# ─────────────────────────────────────────────────────────────

def _render_insider_tab(ticker: str):
    st.subheader("Insider Transactions")
    st.caption(
        "SEC Form 4 filings — purchases and sales by corporate insiders "
        "(executives, directors, 10%+ holders). Insider buying is historically bullish."
    )

    if not ticker:
        st.info("Enter a ticker symbol above to see insider transactions.")
        return

    cache_key = f"flow_data_insider_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading insider data for {ticker}…"):
            ins = get_insider_flow(ticker)
            st.session_state[cache_key] = ins

    ins = st.session_state.get(cache_key, [])

    if not ins:
        st.info(f"No insider transactions found for {ticker}.")
        return

    buys  = [i for i in ins if "BUY" in i["transaction"].upper() or "PURCHASE" in i["transaction"].upper()]
    sells = [i for i in ins if "SELL" in i["transaction"].upper() or "SALE" in i["transaction"].upper()]

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Transactions", len(ins))
    c2.metric("Insider Buys",  len(buys),  delta="Bullish signal" if buys else None)
    c3.metric("Insider Sells", len(sells), delta_color="inverse" if sells else "off",
              delta="Watch" if sells else None)

    rows = []
    for i in ins:
        tx = i["transaction"].upper()
        tx_emoji = "🟢" if "BUY" in tx or "PURCHASE" in tx else "🔴" if "SELL" in tx else "⚪"
        rows.append({
            "Name":        i["name"],
            "Title":       i["title"][:30] if i["title"] else "—",
            "Transaction": f"{tx_emoji} {i['transaction'].title()}",
            "Shares":      f"{i['shares']:,}" if i["shares"] else "—",
            "Price":       f"${i['price']:,.2f}" if i["price"] else "—",
            "Value":       f"${i['notional']:,.0f}" if i["notional"] else "—",
            "Date":        i["date"],
            "Filed":       i["filing_date"] or "—",
        })

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ─────────────────────────────────────────────────────────────
# Demo mode (no API key)
# ─────────────────────────────────────────────────────────────

def _render_demo_mode():
    """Show sample data layout when no API key is configured."""
    st.markdown("---")
    st.markdown("### 📋 What you'll see with an Unusual Whales API key:")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
**🌊 Live Options Flow**
- Real-time unusual call/put activity
- Sweep detection (aggressive multi-exchange fills)
- Block orders (large single trades)
- Premium by ticker heatmap
- Filter by size, type, aggressiveness

**🌑 Dark Pool Prints**
- Off-exchange block trades as they print
- Price level clustering chart
- Institutional accumulation signals
- Support/resistance level detection
""")
    with col2:
        st.markdown("""
**📊 Flow Sentiment**
- Put/call ratio with interpretation
- Call vs put premium donut chart
- Gamma exposure (GEX) levels
- GEX flip level — key volatility trigger

**🏦 Insider Transactions**
- SEC Form 4 filings in real time
- Executive buy/sell with share counts
- Filing delay tracking
- Historically bullish insider buy signals
""")

    st.info(
        "**To activate:** Add `UNUSUAL_WHALES_API_KEY = \"your-key\"` to your "
        "Streamlit secrets (Settings → Secrets on Streamlit Cloud, "
        "or `.streamlit/secrets.toml` locally). "
        "API plans start at $30/month at unusualwhales.com/pricing."
    )