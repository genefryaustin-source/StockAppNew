"""
modules/options_flow/flow_ui.py

Options Flow & Dark Pool Intelligence — Streamlit UI.

Free tier (always works):
  📊 Options Analysis    — P/C ratio, max pain, IV rank, unusual volume from Yahoo Finance
  🌑 Dark Pool (FINRA)   — Official weekly ATS dark pool volume + z-score anomaly detection
  🏦 Insider Flow        — SEC Form 4 transactions via Finnhub

Paid upgrade (Unusual Whales API key):
  🌊 Live Flow Alerts    — real-time unusual options activity with sweep/block detection
  🌑 Dark Pool (Live)    — tick-level dark pool prints

Add to app.py:
    elif page == "Options Flow":
        from modules.options_flow.flow_ui import render_options_flow_page
        render_options_flow_page(db, user)
"""

from __future__ import annotations

from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from modules.options.options_refresh_framework import render_refresh_controls

from modules.options_flow.flow_service import (
    unusual_whales_available,
    get_options_summary,
    get_options_chain,
    get_finra_dark_pool,
    get_insider_transactions,
    get_realtime_flow_alerts,
    get_realtime_darkpool,
)


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_options_flow_page(db, user: dict):
    st.header("🌊 Options Flow & Dark Pool Intelligence")

    uw_live = unusual_whales_available()

    if uw_live:
        st.caption(
            "Real-time options flow · Dark pool prints · Unusual Whales live data enabled · "
            "FINRA ATS dark pool analytics · Insider transactions"
        )
    else:
        st.caption(
            "Options analytics from Yahoo Finance · FINRA ATS dark pool (official, free) · "
            "Insider transactions via Finnhub  ·  "
            "Add UNUSUAL_WHALES_API_KEY to unlock real-time flow alerts"
        )
        st.info(
            "💡 **Free mode active.** "
            "All analytics computed from Yahoo Finance options chain data + official FINRA ATS dark pool data. "
            "Add `UNUSUAL_WHALES_API_KEY` to Streamlit secrets to unlock real-time flow alerts and live dark pool prints "
            "([pricing](https://unusualwhales.com/pricing?product=api))."
        )

    # Ticker input
    col_sym, col_ref = st.columns([3, 1])
    with col_sym:
        ticker = st.text_input(
            "Symbol",
            value="NVDA",
            placeholder="AAPL, NVDA, SPY…",
            key="flow_ticker",
        ).upper().strip()
    with col_ref:
        refresh_state = render_refresh_controls(
            "options_flow",
            ticker,
            cache_prefixes=["flow_cache_"],
            default_mode="1 Minute",
        )
        if refresh_state.force_refresh:
            try:
                from modules.options_flow import flow_service as _flow_service
                if hasattr(_flow_service, "_CACHE"):
                    _flow_service._CACHE.clear()
            except Exception:
                pass

    if not ticker:
        st.info("Enter a ticker symbol to begin.")
        return

    # Build tabs
    if uw_live:
        tab_live, tab_analysis, tab_dark, tab_insider = st.tabs([
            "🌊 Live Flow Alerts",
            "📊 Options Analysis",
            "🌑 Dark Pool",
            "🏦 Insider Transactions",
        ])
        with tab_live:
            _render_live_flow_tab(ticker)
    else:
        tab_analysis, tab_dark, tab_insider = st.tabs([
            "📊 Options Analysis",
            "🌑 Dark Pool",
            "🏦 Insider Transactions",
        ])

    with tab_analysis:
        _render_options_analysis_tab(ticker)

    with tab_dark:
        _render_darkpool_tab(ticker)

    with tab_insider:
        _render_insider_tab(ticker)


# ─────────────────────────────────────────────────────────────
# Tab — Live Flow (Unusual Whales, paid only)
# ─────────────────────────────────────────────────────────────

def _render_live_flow_tab(ticker: str):
    st.subheader(f"🌊 Live Options Flow Alerts — {ticker}")
    st.caption("Real-time unusual options activity · Sweeps, blocks, large premium trades")

    min_prem = st.selectbox(
        "Min premium",
        [10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000],
        index=2,
        format_func=lambda x: f"${x:,.0f}",
        key="flow_min_prem",
    )

    cache_key = f"flow_cache_live_{ticker}_{min_prem}"
    if cache_key not in st.session_state:
        with st.spinner("Fetching live flow…"):
            flow = get_realtime_flow_alerts(ticker, limit=100)
            st.session_state[cache_key] = flow

    flow = st.session_state.get(cache_key, [])
    flow = [f for f in flow if f.get("premium", 0) >= min_prem]

    if not flow:
        st.info("No unusual flow above that premium threshold. Try lowering the minimum.")
        return

    calls = [f for f in flow if f.get("type") == "CALL"]
    puts  = [f for f in flow if f.get("type") == "PUT"]
    sweeps= [f for f in flow if f.get("is_sweep")]
    blocks= [f for f in flow if f.get("is_block")]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total",   len(flow))
    c2.metric("Calls/Puts", f"{len(calls)}/{len(puts)}")
    c3.metric("Sweeps",  len(sweeps))
    c4.metric("Blocks",  len(blocks))

    col_type, col_trade = st.columns(2)
    with col_type:
        type_f = st.radio("Type", ["All","Calls","Puts"], horizontal=True, key="lf_type")
    with col_trade:
        trade_f= st.radio("Filter", ["All","Sweeps","Blocks"], horizontal=True, key="lf_trade")

    filtered = flow
    if type_f  == "Calls":  filtered = [f for f in filtered if f["type"] == "CALL"]
    if type_f  == "Puts":   filtered = [f for f in filtered if f["type"] == "PUT"]
    if trade_f == "Sweeps": filtered = [f for f in filtered if f["is_sweep"]]
    if trade_f == "Blocks": filtered = [f for f in filtered if f["is_block"]]

    rows = []
    for f in filtered[:100]:
        rows.append({
            "Time":    f["timestamp"][:16],
            "Type":    f"{'🟢' if f['type']=='CALL' else '🔴'} {f['type']}",
            "Strike":  f"${f['strike']:,.0f}" if f["strike"] else "—",
            "Expiry":  f["expiry"],
            "Premium": f["premium_fmt"],
            "Size":    f"{f['size']:,}",
            "Flags":   ("⚡SWEEP " if f["is_sweep"] else "") + ("🧱BLOCK" if f["is_block"] else ""),
            "Side":    f["side"],
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    _render_flow_premium_chart(filtered, ticker)


# ─────────────────────────────────────────────────────────────
# Tab — Options Analysis (FREE)
# ─────────────────────────────────────────────────────────────

def _render_options_analysis_tab(ticker: str):
    st.subheader(f"📊 Options Analysis — {ticker}")
    st.caption(
        "Put/call ratio · Max pain · IV rank · Unusual volume spikes · "
        "Net premium flow · All computed from Yahoo Finance options chain"
    )

    cache_key = f"flow_cache_analysis_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading options chain for {ticker}…"):
            summary = get_options_summary(ticker)
            st.session_state[cache_key] = summary

    s = st.session_state.get(cache_key, {})

    if "error" in s:
        err = s["error"]
        if "rate limit" in err.lower() or "too many" in err.lower():
            st.warning(
                "⏳ **Yahoo Finance rate limited.** "
                "This happens when options data is requested too quickly. "
                "Wait 60 seconds then click **↺ Refresh** above."
            )
            st.info(
                "💡 **Tip:** The data caches for 30 minutes once loaded — "
                "this only happens on the first load per session or after a refresh."
            )
        elif "yfinance" in err.lower():
            st.error("yfinance not installed.")
            st.code("pip install yfinance", language="bash")
        else:
            st.error(f"Options data unavailable: {err}")
        return

    spot    = s.get("spot", 0)
    pc_vol  = s.get("pc_vol", 0)
    pc_oi   = s.get("pc_oi", 0)
    pc_sent = s.get("pc_sentiment", "Neutral")
    max_pain= s.get("max_pain")
    iv_rank = s.get("iv_rank", 0)
    iv_med  = s.get("iv_median", 0)
    net_prem= s.get("net_premium", 0)
    net_sent= s.get("net_sentiment", "")

    # ── Key metrics ───────────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Spot Price",   f"${spot:,.2f}" if spot else "—")
    c2.metric("P/C Ratio (Vol)",
              f"{pc_vol:.2f}",
              delta=pc_sent,
              delta_color="normal" if "Bullish" in pc_sent else "inverse" if "Bearish" in pc_sent else "off")
    c3.metric("P/C Ratio (OI)", f"{pc_oi:.2f}")
    c4.metric("Max Pain",     f"${max_pain:,.2f}" if max_pain else "—",
              help="Price where maximum number of options expire worthless at expiry")
    c5.metric("IV Rank",      f"{iv_rank:.0f}%",
              delta="High IV" if iv_rank > 70 else "Low IV" if iv_rank < 30 else "Normal",
              delta_color="inverse" if iv_rank > 70 else "normal" if iv_rank < 30 else "off")
    c6.metric("Median IV",    f"{iv_med:.0f}%")

    # Net premium sentiment
    net_color = "🟢" if net_prem > 0 else "🔴"
    st.markdown(
        f"**Net Premium Flow:** {net_color} "
        f"Calls ${s.get('call_premium',0)/1e6:.1f}M vs Puts ${s.get('put_premium',0)/1e6:.1f}M "
        f"→ **{net_sent}** (${abs(net_prem)/1e6:.1f}M net call premium)"
    )

    # ── P/C ratio donut ───────────────────────────────────────
    call_vol = s.get("call_volume", 0)
    put_vol  = s.get("put_volume", 0)
    if call_vol + put_vol > 0:
        col_chart, col_oi = st.columns(2)
        with col_chart:
            _render_pc_donut(call_vol, put_vol, ticker, "Volume")
        with col_oi:
            _render_pc_donut(s.get("call_oi",0), s.get("put_oi",0), ticker, "Open Interest")

    # ── Max pain vs spot ─────────────────────────────────────
    if max_pain and spot:
        mp_delta = round((max_pain - spot) / spot * 100, 2)
        st.info(
            f"📌 **Max Pain Analysis:** Max pain at ${max_pain:,.2f} "
            f"({'above' if mp_delta > 0 else 'below'} spot by {abs(mp_delta):.1f}%). "
            + ("Options market makers profit most if price stays near max pain by expiry." if abs(mp_delta) < 3
               else f"{'Upward' if mp_delta > 0 else 'Downward'} pressure toward max pain expected as expiry approaches.")
        )

    # ── Unusual volume contracts ──────────────────────────────
    unusual = s.get("unusual_contracts", [])
    if unusual:
        st.markdown("#### 🔥 Unusual Volume — High Vol/OI Ratio Contracts")
        st.caption(
            "Volume/OI ratio > 2× with volume > 200 contracts. "
            "This is the same signal that paid flow tools charge for — "
            "computed directly from the public options chain."
        )

        rows = []
        for u in unusual:
            rows.append({
                "Type":      f"{'🟢 CALL' if u['type']=='CALL' else '🔴 PUT'}",
                "Strike":    f"${u['strike']:,.0f}",
                "Expiry":    u["expiry"],
                "Volume":    f"{u['volume']:,}",
                "OI":        f"{u['open_interest']:,}",
                "Vol/OI":    f"{u['vol_oi_ratio']:.1f}×",
                "IV":        f"{u['iv_pct']:.0f}%",
                "OTM%":      f"{u['otm_pct']:+.1f}%",
                "Est Premium": u["premium_fmt"],
                "Sentiment": u["sentiment"],
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            "📝 Vol/OI > 2× means more contracts traded today than currently open — "
            "someone is opening significant new positions aggressively. "
            "High OTM + high premium = high conviction directional bet."
        )


def _render_pc_donut(call_val: float, put_val: float, ticker: str, label: str):
    if call_val + put_val == 0:
        return
    total    = call_val + put_val
    call_pct = call_val / total * 100
    put_pct  = 100 - call_pct

    fig, ax = plt.subplots(figsize=(3.5, 3.5), facecolor="#0F1117")
    ax.set_facecolor("#0F1117")
    wedges, _, autotexts = ax.pie(
        [call_pct, put_pct],
        autopct="%1.0f%%",
        colors=["#1D9E75", "#E24B4A"],
        startangle=90,
        wedgeprops={"linewidth": 2, "edgecolor": "#0F1117"},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(10)

    circle = plt.Circle((0, 0), 0.55, fc="#0F1117")
    ax.add_artist(circle)
    sentiment = "Bullish" if call_pct > 55 else "Bearish" if put_pct > 55 else "Mixed"
    ax.text(0, 0.1, sentiment, ha="center", va="center",
            fontsize=10, color="white", fontweight="bold")
    ax.text(0, -0.2, f"P/C {put_val/call_val:.2f}" if call_val > 0 else "",
            ha="center", va="center", fontsize=8, color="#8B949E")

    ax.legend(["Calls", "Puts"], loc="lower center", fontsize=8,
              facecolor="#0F1117", labelcolor="white", framealpha=0.2,
              ncol=2, bbox_to_anchor=(0.5, -0.1))
    ax.set_title(f"{ticker} {label}", color="white", fontsize=10, pad=6)
    plt.tight_layout()
    st.pyplot(fig, use_container_width=False)
    plt.close(fig)


def _render_flow_premium_chart(flow: list, ticker: str):
    if not flow or len(flow) < 2:
        return
    by_type = {"CALL": 0, "PUT": 0}
    for f in flow:
        by_type[f.get("type", "CALL")] = by_type.get(f.get("type","CALL"), 0) + f.get("premium", 0)

    fig, ax = plt.subplots(figsize=(6, 2.5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    bars = ax.bar(["Calls", "Puts"],
                  [by_type["CALL"]/1e3, by_type["PUT"]/1e3],
                  color=["#1D9E75","#E24B4A"], alpha=0.85)
    ax.set_ylabel("Premium ($K)", color="#8B949E", fontsize=8)
    ax.set_title(f"{ticker} Flow Premium Split", color="#C9D1D9", fontsize=9)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.4)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Tab — Dark Pool (FINRA + optional Unusual Whales)
# ─────────────────────────────────────────────────────────────

def _render_darkpool_tab(ticker: str):
    st.subheader(f"🌑 Dark Pool Activity — {ticker}")

    uw_live = unusual_whales_available()

    if uw_live:
        source = st.radio(
            "Data source",
            ["🔴 Live (Unusual Whales)", "📊 Weekly Aggregate (FINRA ATS)"],
            horizontal=True,
            key="dp_source",
        )
        if "Live" in source:
            _render_darkpool_live(ticker)
            return

    _render_darkpool_finra(ticker)


def _render_darkpool_live(ticker: str):
    st.caption("Real-time dark pool prints via Unusual Whales")
    cache_key = f"flow_cache_dp_live_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner("Fetching dark pool data…"):
            dp = get_realtime_darkpool(ticker, limit=100)
            st.session_state[cache_key] = dp

    dp = st.session_state.get(cache_key, [])
    if not dp:
        st.info("No dark pool prints found for this ticker.")
        return

    total_notional = sum(f["notional"] for f in dp)
    c1, c2, c3 = st.columns(3)
    c1.metric("Prints",         len(dp))
    c2.metric("Total Notional", f"${total_notional/1e6:.1f}M")
    c3.metric("Largest Print",  dp[0]["notional_fmt"] if dp else "—")

    rows = [{"Time": f["time"], "Price": f"${f['price']:,.2f}",
             "Size": f"{f['size']:,}", "Notional": f["notional_fmt"]}
            for f in dp[:100]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    _render_darkpool_levels(dp, ticker)


def _render_darkpool_finra(ticker: str):
    st.caption(
        "**Official FINRA ATS Transparency Data** — the same source all paid tools use. "
        "Weekly aggregate (~1 week delay). Z-score flags unusually high dark pool activity."
    )

    cache_key = f"flow_cache_dp_finra_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Fetching FINRA ATS data for {ticker}…"):
            data = get_finra_dark_pool(ticker)
            st.session_state[cache_key] = data

    data = st.session_state.get(cache_key, {})

    if "error" in data:
        st.warning(f"Dark pool data unavailable: {data['error']}")
        return

    source = data.get("source", "finra_api")

    # ── Proxy mode (no FINRA key) ─────────────────────────────
    if source == "proxy":
        inst_score = data.get("inst_score", 0)
        sig        = data.get("signal", "")
        pc_oi      = data.get("pc_oi", 1.0)
        iv_rank    = data.get("iv_rank", 50)
        total_prem = data.get("total_premium", 0)

        score_color = "#E24B4A" if inst_score > 70 else "#BA7517" if inst_score > 40 else "#1D9E75"
        st.markdown(
            f"**Institutional Activity Score: "
            f"<span style='color:{score_color}'>{inst_score:.0f}/100</span>** — {sig}",
            unsafe_allow_html=True,
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("P/C OI Ratio",     f"{pc_oi:.2f}",
                  help="Put/Call open interest ratio — >1.3 = heavy put hedging by institutions")
        c2.metric("IV Rank",          f"{iv_rank:.0f}%",
                  help="High IV rank = elevated options premiums = institutional activity")
        c3.metric("Total Options $",  f"${total_prem/1e6:.0f}M" if total_prem else "—",
                  help="Total estimated premium across all open contracts")

        st.info(data.get("data_note", ""))
        st.markdown(
            "**To get real dark pool data (free):**\n\n"
            "1. Register at [developer.finra.org](https://developer.finra.org) (free account)\n"
            "2. Create an API application → get Client ID and Secret\n"
            "3. Add to Streamlit secrets: `FINRA_API_KEY = clientid:secret`\n\n"
            "This gives you official weekly ATS dark pool volume for every US-listed security."
        )
        return

    # ── Real FINRA data mode ──────────────────────────────────
    z    = data.get("z_score", 0) or 0
    sig  = data.get("signal", "")
    dpct = data.get("dark_pct", 0) or 0
    mean_dpct = data.get("mean_dark_pct", 0) or 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest Week",   data.get("latest_week", "—"))
    c2.metric("Dark Pool Vol", f"{data.get('dark_vol', 0):,}")

    # Show dark pool % if meaningful (market vol available), else show raw vol context
    has_real_pct = dpct > 0 and dpct < 100
    c3.metric(
        "Dark Pool %" if has_real_pct else "ATS Volume",
        f"{dpct:.2f}%" if has_real_pct else f"{data.get('dark_vol',0)/1e6:.1f}M shares",
        delta=f"avg {mean_dpct:.2f}%" if has_real_pct else None,
        delta_color="inverse" if z > 1.5 else "off",
    )
    c4.metric("Z-Score",       f"{z:+.2f}",
              delta="Unusual!" if abs(z) > 1.5 else "Normal",
              delta_color="inverse" if z > 1.5 else "normal" if z < -1.5 else "off")

    if z > 1.5:
        st.warning(
            f"🔴 **{sig}** — Dark pool volume is {z:.1f} standard deviations above average "
            f"({dpct:.1f}% vs {mean_dpct:.1f}% typical). "
            "This level of off-exchange activity may indicate institutional accumulation or distribution."
        )
    elif z > 0.5:
        st.info(f"🟡 {sig} — Slightly elevated dark pool activity this week.")
    else:
        st.success(f"🟢 {sig} — Dark pool activity within normal range.")

    history = data.get("weekly_history", [])
    if len(history) >= 2:
        _render_darkpool_history_chart(history, ticker, mean_dpct)

    st.caption(data.get("data_note", ""))


def _render_darkpool_history_chart(history: list, ticker: str, mean_pct: float):
    weeks  = [h["week"] for h in reversed(history)]
    dpcts  = [h["dark_pct"] for h in reversed(history)]

    fig, ax = plt.subplots(figsize=(10, 3), facecolor="#0F1117")
    ax.set_facecolor("#161B22")

    colors = ["#E24B4A" if d > mean_pct * 1.2 else "#1D9E75" for d in dpcts]
    ax.bar(range(len(weeks)), dpcts, color=colors, alpha=0.8)
    ax.axhline(mean_pct, color="#8B949E", linewidth=1.2, linestyle="--",
               label=f"Average {mean_pct:.1f}%")

    ax.set_xticks(range(len(weeks)))
    ax.set_xticklabels([w[5:] for w in weeks], rotation=45, ha="right",
                       fontsize=7, color="#8B949E")
    ax.set_ylabel("Dark Pool %", color="#8B949E", fontsize=8)
    ax.set_title(f"{ticker} Weekly Dark Pool % (FINRA ATS)",
                 color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.4, alpha=0.5)
    ax.legend(fontsize=8, facecolor="#0F1117", labelcolor="#8B949E",
              framealpha=0.3)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def _render_darkpool_levels(dp: list, ticker: str):
    prices   = [f["price"] for f in dp if f.get("price")]
    notionals= [f["notional"] for f in dp if f.get("price")]
    if len(prices) < 2:
        return

    st.markdown("#### Price Level Clusters")
    fig, ax = plt.subplots(figsize=(10, 2.5), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    sizes = [max(20, n / max(notionals) * 600) for n in notionals]
    ax.scatter(prices, [1]*len(prices), s=sizes, c="#378ADD", alpha=0.6)
    for p, s in zip(prices, sizes):
        if s > 150:
            ax.axvline(p, color="#378ADD", linewidth=0.5, alpha=0.3)
    ax.set_xlabel("Price ($)", color="#8B949E", fontsize=8)
    ax.set_yticks([])
    ax.set_title(f"{ticker} Dark Pool Price Levels (bubble = notional size)",
                 color="#C9D1D9", fontsize=9)
    ax.spines[:].set_color("#21262D")
    ax.tick_params(colors="#8B949E")
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Tab — Insider Transactions
# ─────────────────────────────────────────────────────────────

def _render_insider_tab(ticker: str):
    st.subheader(f"🏦 Insider Transactions — {ticker}")
    st.caption(
        "SEC Form 4 filings — purchases and sales by executives, directors, and 10%+ holders. "
        "Powered by your existing Finnhub API key."
    )

    cache_key = f"flow_cache_insider_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Loading insider data for {ticker}…"):
            ins = get_insider_transactions(ticker)
            st.session_state[cache_key] = ins

    ins = st.session_state.get(cache_key, [])

    if not ins:
        st.info(
            f"No insider transaction data for {ticker}. "
            "Ensure FINNHUB_API_KEY is set in your secrets."
        )
        return

    buys  = [i for i in ins if i.get("is_buy")]
    sells = [i for i in ins if not i.get("is_buy")]

    c1, c2, c3 = st.columns(3)
    c1.metric("Transactions",  len(ins))
    c2.metric("Insider Buys",  len(buys),
              delta="Bullish" if buys else None, delta_color="normal")
    c3.metric("Insider Sells", len(sells),
              delta="Watch" if len(sells) > len(buys) else None,
              delta_color="inverse" if len(sells) > len(buys) else "off")

    rows = []
    for i in ins:
        icon = "🟢 BUY" if i["is_buy"] else "🔴 SELL"
        rows.append({
            "Date":    i["date"],
            "Name":    i["name"],
            "Action":  icon,
            "Shares":  f"{abs(i['shares']):,}",
            "Price":   f"${i['price']:,.2f}" if i["price"] else "—",
            "Value":   f"${i['value']:,.0f}" if i["value"] else "—",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if buys and not sells:
        st.success(
            "📈 **Pure insider buying** — no insider sales recently. "
            "Historically, clusters of insider purchases are one of the most reliable bullish signals."
        )
    elif sells and len(sells) > len(buys) * 2:
        st.warning(
            "📉 **Heavy insider selling** — significantly more sell transactions than buys. "
            "Could reflect stock compensation selling or genuine distribution."
        )