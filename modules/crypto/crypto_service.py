"""
modules/crypto/service.py — entry point, imports crypto_service + builds full UI
"""
from modules.crypto.crypto_service import (
    get_top_coins, get_coin_detail, get_coin_history,
    get_global_stats, get_trending, get_fear_greed,
    get_defi_protocols, search_coin, CATEGORIES, COIN_SYMBOLS,
)
from modules.crypto.crypto_ai import (
    generate_market_narrative, analyze_coin, advise_portfolio,
    detect_trends, scan_crypto_risks,
)
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY = True
except ImportError:
    PLOTLY = False

CALL_CLR = "#F7931A"   # Bitcoin orange
ETH_CLR  = "#627EEA"   # Ethereum purple
GREEN    = "#1D9E75"
RED      = "#E24B4A"


def render_crypto_page(db, user):
    st.header("🪙 Crypto Markets")
    st.caption(
        "Top 100+ coins · Fear & Greed · DeFi TVL · AI Market Narrative · "
        "Coin Analysis · Portfolio Advisor · Trend Detector · Risk Scanner · "
        "Powered by CoinGecko + DeFi Llama + Alternative.me"
    )

    tabs = st.tabs([
        "📊 Market Overview",
        "🔍 Coin Detail",
        "🏦 DeFi & NFT",
        "🤖 AI Analysis",
        "📈 Portfolio Tracker",
    ])

    with tabs[0]: _render_market_overview()
    with tabs[1]: _render_coin_detail()
    with tabs[2]: _render_defi()
    with tabs[3]: _render_ai_analysis()
    with tabs[4]: _render_portfolio_tracker()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════

def _render_market_overview():
    st.subheader("📊 Crypto Market Overview")

    col_cat, col_lim, col_r = st.columns([2, 1, 1])
    with col_cat:
        category = st.selectbox("Category", CATEGORIES, key="crypto_cat")
    with col_lim:
        limit = st.selectbox("Show", [25, 50, 100, 200], index=1, key="crypto_lim")
    with col_r:
        st.write("")
        if st.button("↺ Refresh", key="crypto_refresh", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("crypto_"): del st.session_state[k]

    # Global stats
    cache_key = "crypto_global"
    if cache_key not in st.session_state:
        with st.spinner("Loading global stats…"):
            st.session_state[cache_key] = get_global_stats()
    g = st.session_state[cache_key]

    if g:
        btc_dom   = g.get("bitcoin_dominance_percentage", 0)
        eth_dom   = g.get("ethereum_dominance_percentage", 0)
        total_mc  = g.get("total_market_cap", {}).get("usd", 0)
        mc_chg    = g.get("market_cap_change_percentage_24h_usd", 0)
        total_vol = g.get("total_volume", {}).get("usd", 0)
        n_coins   = g.get("active_cryptocurrencies", 0)

        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Market Cap",   f"${total_mc/1e12:.2f}T",
                  f"{mc_chg:+.1f}%",
                  delta_color="normal" if mc_chg >= 0 else "inverse")
        c2.metric("24h Volume",         f"${total_vol/1e9:.0f}B")
        c3.metric("BTC Dominance",      f"{btc_dom:.1f}%")
        c4.metric("ETH Dominance",      f"{eth_dom:.1f}%")
        c5.metric("Active Coins",       f"{n_coins:,}")

    # Fear & Greed
    fg_key = "crypto_fg"
    if fg_key not in st.session_state:
        st.session_state[fg_key] = get_fear_greed(30)
    fg_df = st.session_state[fg_key]

    if not fg_df.empty:
        latest_fg    = int(fg_df["value"].iloc[-1])
        latest_label = fg_df["classification"].iloc[-1]
        fg_color = (GREEN if latest_fg > 60 else RED if latest_fg < 40 else "#BA7517")
        fg_icon  = "🟢" if latest_fg > 60 else "🔴" if latest_fg < 40 else "🟡"

        col_fg, col_fgchart = st.columns([1, 3])
        with col_fg:
            st.markdown(
                f"<h2 style='color:{fg_color};margin:0'>{fg_icon} {latest_fg}</h2>"
                f"<p style='color:#8B949E;margin:0'>Fear & Greed: <b>{latest_label}</b></p>",
                unsafe_allow_html=True,
            )
        with col_fgchart:
            if PLOTLY:
                fig = go.Figure(go.Scatter(
                    x=fg_df["timestamp"], y=fg_df["value"],
                    fill="tozeroy",
                    fillcolor="rgba(247,147,26,0.1)",
                    line=dict(color=CALL_CLR, width=2),
                    hovertemplate="%{y} — %{x|%b %d}<extra></extra>",
                ))
                fig.add_hline(y=50, line_dash="dot", line_color="#4A5568")
                fig.update_layout(
                    height=100, margin=dict(l=0,r=0,t=5,b=5),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False, yaxis=dict(range=[0,100], showgrid=False),
                    xaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    st.divider()

    # Top coins table
    coins_key = f"crypto_top_{category}_{limit}"
    if coins_key not in st.session_state:
        with st.spinner(f"Loading {limit} coins…"):
            st.session_state[coins_key] = get_top_coins(limit, category)
    df = st.session_state[coins_key]

    if df.empty:
        st.warning("Failed to load coin data. CoinGecko may be rate-limiting.")
        return

    # Trending strip
    tr_key = "crypto_trending"
    if tr_key not in st.session_state:
        st.session_state[tr_key] = get_trending()
    trending = st.session_state[tr_key]
    if trending:
        symbols = " · ".join(f"🔥 {t['Symbol']}" for t in trending[:7])
        st.caption(f"**Trending:** {symbols}")

    # Sort / filter
    col_sort, col_order = st.columns([2, 1])
    with col_sort:
        sort_by = st.selectbox("Sort by",
            ["Market Cap","24h %","7d %","30d %","Volume 24h","Price"],
            key="crypto_sort")
    with col_order:
        ascending = st.checkbox("Ascending", value=False, key="crypto_asc")

    sort_map = {"Market Cap":"Market Cap","24h %":"24h %","7d %":"7d %",
                "30d %":"30d %","Volume 24h":"Volume 24h","Price":"Price"}
    sc = sort_map.get(sort_by, "Market Cap")
    display_df = df.copy()
    if sc in display_df.columns:
        display_df = display_df.sort_values(sc, ascending=ascending, na_position="last")

    # Format
    fmt_df = display_df[["Rank","Symbol","Name","Price","1h %","24h %","7d %",
                           "Market Cap","Volume 24h"]].copy()

    def _fmt_price(v):
        if v is None: return "—"
        if v >= 1000:   return f"${v:,.2f}"
        if v >= 1:      return f"${v:.4f}"
        if v >= 0.0001: return f"${v:.6f}"
        return f"${v:.8f}"

    def _fmt_mcap(v):
        if not v: return "—"
        if v >= 1e12: return f"${v/1e12:.2f}T"
        if v >= 1e9:  return f"${v/1e9:.1f}B"
        return f"${v/1e6:.0f}M"

    def _fmt_pct(v):
        return f"{v:+.2f}%" if v is not None else "—"

    def _color_pct(v):
        try:
            return f"color: {GREEN}" if float(v.replace("%","").replace("+","")) > 0 else \
                   f"color: {RED}"   if float(v.replace("%","").replace("+","")) < 0 else ""
        except: return ""

    fmt_df["Price"]      = fmt_df["Price"].apply(_fmt_price)
    fmt_df["Market Cap"] = fmt_df["Market Cap"].apply(_fmt_mcap)
    fmt_df["Volume 24h"] = fmt_df["Volume 24h"].apply(_fmt_mcap)
    for col in ["1h %","24h %","7d %"]:
        fmt_df[col] = fmt_df[col].apply(_fmt_pct)

    styled = fmt_df.style.applymap(_color_pct, subset=["1h %","24h %","7d %"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=500)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — COIN DETAIL
# ══════════════════════════════════════════════════════════════════════════════

def _render_coin_detail():
    st.subheader("🔍 Coin Deep Dive")

    col_search, col_days = st.columns([3, 1])
    with col_search:
        coin_input = st.text_input("Search coin (name or symbol)",
                                    value="bitcoin", key="coin_search",
                                    placeholder="bitcoin, ETH, solana…")
    with col_days:
        days = st.selectbox("Period", [7, 30, 90, 180, 365, 730],
                             index=3, key="coin_days",
                             format_func=lambda x: f"{x}d" if x < 365 else f"{x//365}y")

    # Resolve coin ID
    if not coin_input:
        st.info("Enter a coin name or symbol.")
        return

    # Check if it's a symbol → find ID
    coin_id = coin_input.lower().strip()
    sym_to_id = {v.lower(): k for k, v in COIN_SYMBOLS.items()}
    if coin_id.upper() in {v.upper() for v in COIN_SYMBOLS.values()}:
        coin_id = sym_to_id.get(coin_id, coin_id)
    elif coin_id not in COIN_SYMBOLS:
        # Search
        results = search_coin(coin_input)
        if results:
            coin_id = results[0]["id"]
        else:
            st.warning(f"Coin '{coin_input}' not found.")
            return

    detail_key = f"coin_detail_{coin_id}"
    hist_key   = f"coin_hist_{coin_id}_{days}"

    if detail_key not in st.session_state:
        with st.spinner(f"Loading {coin_id}…"):
            st.session_state[detail_key] = get_coin_detail(coin_id)
    if hist_key not in st.session_state:
        with st.spinner("Loading history…"):
            st.session_state[hist_key] = get_coin_history(coin_id, days)

    detail = st.session_state[detail_key]
    hist   = st.session_state[hist_key]

    if not detail:
        st.error(f"No data for '{coin_id}'.")
        return

    md    = detail.get("market_data", {})
    price = md.get("current_price", {}).get("usd", 0)
    ch24  = md.get("price_change_percentage_24h", 0)
    ch7d  = md.get("price_change_percentage_7d", 0)
    ch30  = md.get("price_change_percentage_30d", 0)
    mcap  = md.get("market_cap", {}).get("usd", 0)
    vol   = md.get("total_volume", {}).get("usd", 0)
    ath   = md.get("ath", {}).get("usd", 0)
    ath_pct = md.get("ath_change_percentage", {}).get("usd", 0)
    circ  = md.get("circulating_supply", 0)
    max_s = md.get("max_supply")
    name  = detail.get("name","")
    symbol= detail.get("symbol","").upper()

    # Header
    st.markdown(f"## {name} ({symbol})")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.metric("Price",    f"${price:,.4f}" if price < 10 else f"${price:,.2f}",
              f"{ch24:+.2f}%",
              delta_color="normal" if ch24 >= 0 else "inverse")
    c2.metric("7d",       f"{ch7d:+.2f}%",
              delta_color="normal" if ch7d >= 0 else "inverse")
    c3.metric("30d",      f"{ch30:+.2f}%",
              delta_color="normal" if ch30 >= 0 else "inverse")
    c4.metric("Market Cap", f"${mcap/1e9:.1f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M")
    c5.metric("ATH",      f"${ath:,.2f}", f"{ath_pct:.1f}% from ATH",
              delta_color="normal" if ath_pct >= -10 else "inverse")

    c6,c7,c8 = st.columns(3)
    c6.metric("Volume 24h",    f"${vol/1e9:.2f}B" if vol >= 1e9 else f"${vol/1e6:.0f}M")
    c7.metric("Circulating",   f"{circ/1e9:.2f}B" if circ >= 1e9 else f"{circ/1e6:.0f}M {symbol}")
    c8.metric("Max Supply",    f"{max_s/1e9:.2f}B" if max_s and max_s >= 1e9
              else f"{max_s/1e6:.0f}M" if max_s else "Unlimited")

    # Description
    desc = detail.get("description", {}).get("en", "")
    if desc:
        with st.expander("About", expanded=False):
            import re
            clean_desc = re.sub('<[^<]+?>', '', desc)[:600]
            st.markdown(clean_desc + "…")

    # Price chart
    if not hist.empty and PLOTLY:
        _render_coin_chart(hist, name, symbol, days)

    # AI Analysis button
    st.divider()
    if st.button(f"🤖 Generate AI Analysis for {symbol}", key=f"ai_coin_{coin_id}",
                  type="primary"):
        with st.spinner(f"Analyzing {name}…"):
            analysis = analyze_coin(
                coin_id=coin_id, symbol=symbol, name=name,
                price=price, change_24h=ch24, change_7d=ch7d,
                market_cap=mcap, volume_24h=vol,
                ath=ath, ath_pct=ath_pct,
                circulating_supply=circ,
                community_score=detail.get("community_score"),
                developer_score=detail.get("developer_score"),
                description=desc,
            )
        st.session_state[f"coin_analysis_{coin_id}"] = analysis

    if ai := st.session_state.get(f"coin_analysis_{coin_id}"):
        st.info(ai)


def _render_coin_chart(df: pd.DataFrame, name: str, symbol: str, days: int):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )
    date_col = "Date"

    if "open" in df.columns:
        fig.add_trace(go.Candlestick(
            x=df[date_col], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="Price",
            increasing_line_color=GREEN, decreasing_line_color=RED,
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df["close"],
            line=dict(color=CALL_CLR, width=2),
            fill="tozeroy", fillcolor="rgba(247,147,26,0.07)",
            name="Price",
        ), row=1, col=1)

    # EMA 20
    if len(df) > 20:
        ema = df["close"].ewm(span=20).mean()
        fig.add_trace(go.Scatter(
            x=df[date_col], y=ema, line=dict(color="#2196F3", width=1.2, dash="dot"),
            name="EMA 20",
        ), row=1, col=1)

    # Volume
    if "volume" in df.columns:
        fig.add_trace(go.Bar(
            x=df[date_col], y=df["volume"],
            marker_color=CALL_CLR, opacity=0.5, name="Volume",
        ), row=2, col=1)

    fig.update_layout(
        title=f"{name} ({symbol}) — {days}d",
        template="plotly_dark",
        paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
        height=500, margin=dict(l=0,r=20,t=40,b=20),
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02),
    )
    fig.update_xaxes(gridcolor="#21262D")
    fig.update_yaxes(gridcolor="#21262D")
    st.plotly_chart(fig, use_container_width=True,
                    config={"scrollZoom": True, "displayModeBar": True})


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — DeFi & NFT
# ══════════════════════════════════════════════════════════════════════════════

def _render_defi():
    st.subheader("🏦 DeFi & On-Chain")
    st.caption("DeFi Llama TVL · Top protocols · Category breakdown")

    if st.button("📡 Load DeFi Data", key="defi_load", type="primary") or \
       st.session_state.get("defi_loaded"):
        st.session_state["defi_loaded"] = True

        if "defi_protocols" not in st.session_state:
            with st.spinner("Loading DeFi TVL data…"):
                st.session_state["defi_protocols"] = get_defi_protocols(50)

        df = st.session_state["defi_protocols"]
        if df.empty:
            st.warning("DeFi Llama data unavailable.")
            return

        total_tvl = df["TVL ($B)"].sum()
        top_chain = df.groupby("Chain")["TVL ($B)"].sum().idxmax() if not df.empty else "—"

        c1,c2,c3 = st.columns(3)
        c1.metric("Total DeFi TVL", f"${total_tvl:.1f}B")
        c2.metric("Top Chain", top_chain)
        c3.metric("Protocols Tracked", len(df))

        tab_all, tab_cat, tab_chain = st.tabs(["All Protocols", "By Category", "By Chain"])

        with tab_all:
            def _pct_color(v):
                try: return f"color: {GREEN}" if float(v.replace("%","")) > 0 else f"color: {RED}"
                except: return ""
            show = df[["Protocol","Category","Chain","TVL ($B)","1d %","7d %","Symbol"]].copy()
            show["1d %"] = show["1d %"].apply(lambda x: f"{x:+.1f}%")
            show["7d %"] = show["7d %"].apply(lambda x: f"{x:+.1f}%")
            styled = show.style.applymap(_pct_color, subset=["1d %","7d %"])
            st.dataframe(styled, use_container_width=True, hide_index=True, height=400)

        with tab_cat:
            cat_df = df.groupby("Category")["TVL ($B)"].sum().sort_values(ascending=False)
            if PLOTLY:
                fig = go.Figure(go.Bar(
                    x=cat_df.index, y=cat_df.values,
                    marker_color=CALL_CLR, opacity=0.8,
                ))
                fig.update_layout(
                    title="DeFi TVL by Category ($B)",
                    template="plotly_dark",
                    paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
                    height=350, margin=dict(l=0,r=0,t=40,b=0),
                )
                st.plotly_chart(fig, use_container_width=True)
            st.dataframe(cat_df.reset_index().rename(
                columns={"Category":"Category","TVL ($B)":"TVL ($B)"}
            ), use_container_width=True, hide_index=True)

        with tab_chain:
            chain_df = df.groupby("Chain")["TVL ($B)"].sum().sort_values(ascending=False).head(15)
            if PLOTLY:
                fig = go.Figure(go.Pie(
                    labels=chain_df.index, values=chain_df.values,
                    hole=0.4,
                ))
                fig.update_layout(
                    title="TVL Distribution by Chain",
                    template="plotly_dark",
                    paper_bgcolor="#0F1117",
                    height=400, margin=dict(l=0,r=0,t=40,b=0),
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Click **Load DeFi Data** to fetch TVL and protocol data from DeFi Llama.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — AI ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _render_ai_analysis():
    st.subheader("🤖 AI Crypto Intelligence")

    sub = st.tabs([
        "📰 Market Narrative",
        "🔮 Trend Detector",
        "⚠️ Risk Scanner",
    ])

    with sub[0]: _render_market_narrative()
    with sub[1]: _render_trend_detector()
    with sub[2]: _render_risk_scanner()


def _render_market_narrative():
    st.markdown("#### 📰 AI Market Narrative")
    st.caption("Claude analyzes global market data and generates today's crypto narrative")

    if st.button("🤖 Generate Market Narrative", key="ai_narrative", type="primary"):
        with st.spinner("Loading market data…"):
            g     = get_global_stats()
            fg_df = get_fear_greed(7)
            df    = get_top_coins(50)
            tr    = get_trending()

        fg_val   = int(fg_df["value"].iloc[-1])    if not fg_df.empty else 50
        fg_label = fg_df["classification"].iloc[-1] if not fg_df.empty else "Neutral"

        gainers = []
        losers  = []
        if not df.empty:
            gainers = df.nlargest(5,"24h %")[["Symbol","24h %"]].to_dict("records")
            losers  = df.nsmallest(5,"24h %")[["Symbol","24h %"]].to_dict("records")

        with st.spinner("Generating narrative…"):
            narrative = generate_market_narrative(
                global_stats=g,
                fear_greed_value=fg_val,
                fear_greed_label=fg_label,
                top_gainers=gainers,
                top_losers=losers,
                trending=tr,
                defi_tvl_change=None,
            )
        st.session_state["crypto_narrative"] = narrative

    if n := st.session_state.get("crypto_narrative"):
        st.info(n)


def _render_trend_detector():
    st.markdown("#### 🔮 Emerging Trend Detector")
    st.caption("AI identifies narratives gaining momentum based on price action and search trends")

    if st.button("🔮 Detect Trends", key="ai_trends", type="primary"):
        with st.spinner("Analyzing market trends…"):
            df = get_top_coins(100)
            tr = get_trending()
            top_coins_list = df.to_dict("records") if not df.empty else []

        with st.spinner("AI identifying narratives…"):
            trends = detect_trends(top_coins_list, tr, [])
        st.session_state["crypto_trends"] = trends

    if trends := st.session_state.get("crypto_trends"):
        for t in trends:
            momentum_icons = {"strong":"🔥","moderate":"📈","early":"🌱","unknown":"—"}
            icon = momentum_icons.get(t.get("momentum","unknown"), "—")
            with st.container():
                col_t, col_m = st.columns([4, 1])
                with col_t:
                    coins_str = " · ".join(t.get("coins",[])[:4])
                    st.markdown(
                        f"**{icon} {t.get('theme','')}** — "
                        f"{t.get('rationale','')}"
                    )
                    if coins_str:
                        st.caption(f"Coins: {coins_str}")
                    if t.get("risk"):
                        st.caption(f"⚠️ Risk: {t['risk']}")
                with col_m:
                    st.markdown(f"**{t.get('momentum','—').title()}**")
                st.markdown("---")


def _render_risk_scanner():
    st.markdown("#### ⚠️ AI Risk Scanner")
    st.caption("Flags anomalies across top 50 coins and interprets risk signals")

    if st.button("⚠️ Scan for Risks", key="ai_risks", type="primary"):
        with st.spinner("Loading market data…"):
            df    = get_top_coins(50)
            g     = get_global_stats()
            fg_df = get_fear_greed(1)

        fg_val   = int(fg_df["value"].iloc[-1]) if not fg_df.empty else 50
        mc_chg   = g.get("market_cap_change_percentage_24h_usd", 0)
        btc_row  = df[df["Symbol"]=="BTC"]
        btc_ch24 = float(btc_row["24h %"].iloc[0]) if not btc_row.empty and btc_row["24h %"].iloc[0] is not None else 0

        with st.spinner("AI analyzing risks…"):
            alerts = scan_crypto_risks(
                watchlist_coins=df.to_dict("records") if not df.empty else [],
                fear_greed=fg_val,
                btc_change_24h=btc_ch24,
                market_cap_change=mc_chg,
            )
        st.session_state["crypto_risks"] = alerts

    if alerts := st.session_state.get("crypto_risks"):
        if not alerts:
            st.success("✅ No significant risk anomalies detected.")
            return
        severity_icons = {"low":"🟡","medium":"🟠","high":"🔴","critical":"🚨"}
        action_colors  = {"monitor":"#8B949E","review":"#BA7517","caution":"#E24B4A"}
        for a in alerts:
            icon   = severity_icons.get(a.get("severity","medium"), "⚪")
            action = a.get("action","monitor")
            color  = action_colors.get(action, "#8B949E")
            st.markdown(
                f"{icon} **{a.get('symbol','')}** — {a.get('interpretation','')} "
                f"<span style='color:{color};font-size:11px'>→ {action.upper()}</span>",
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — PORTFOLIO TRACKER
# ══════════════════════════════════════════════════════════════════════════════

def _render_portfolio_tracker():
    st.subheader("📈 Crypto Portfolio Tracker")
    st.caption("Track your holdings · AI portfolio advice · Rebalancing suggestions")

    # Holdings input
    st.markdown("#### Add Holdings")
    st.caption("Enter your holdings to track performance and get AI advice.")

    port_key = "crypto_portfolio"
    if port_key not in st.session_state:
        st.session_state[port_key] = []

    col_sym, col_qty, col_add = st.columns([2, 2, 1])
    with col_sym:
        new_sym = st.text_input("Coin (symbol or name)",
                                 placeholder="BTC, ETH, SOL…", key="port_sym")
    with col_qty:
        new_qty = st.number_input("Quantity", min_value=0.0, step=0.001,
                                   format="%.6f", key="port_qty")
    with col_add:
        st.write("")
        if st.button("Add", key="port_add", type="primary", use_container_width=True):
            if new_sym and new_qty > 0:
                sym = new_sym.upper().strip()
                # Try to find coin ID
                sym_to_id = {v.upper(): k for k, v in COIN_SYMBOLS.items()}
                cid = sym_to_id.get(sym, sym.lower())
                st.session_state[port_key].append({
                    "coin_id": cid, "symbol": sym, "qty": new_qty
                })
                st.rerun()

    holdings = st.session_state[port_key]

    if not holdings:
        st.info("Add holdings above to track your crypto portfolio.")
        return

    # Fetch current prices
    total_value = 0
    enriched = []
    for h in holdings:
        cid = h["coin_id"]
        detail = get_coin_detail(cid)
        if detail:
            md    = detail.get("market_data", {})
            price = md.get("current_price", {}).get("usd", 0) or 0
            ch7d  = md.get("price_change_percentage_7d", 0) or 0
            value = price * h["qty"]
            total_value += value
            enriched.append({**h, "price": price, "value": value, "change_7d": ch7d})
        else:
            enriched.append({**h, "price": 0, "value": 0, "change_7d": 0})

    # Portfolio table
    rows = []
    for e in enriched:
        pct = e["value"] / max(1, total_value) * 100
        rows.append({
            "Symbol":    e["symbol"],
            "Qty":       e["qty"],
            "Price":     f"${e['price']:,.4f}" if e["price"] < 10 else f"${e['price']:,.2f}",
            "Value":     f"${e['value']:,.2f}",
            "Weight":    f"{pct:.1f}%",
            "7d %":      f"{e['change_7d']:+.2f}%",
        })

    c1,c2 = st.columns(2)
    c1.metric("Total Portfolio Value", f"${total_value:,.2f}")
    c2.metric("Assets", len(enriched))

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    col_clear, col_ai = st.columns([1, 2])
    with col_clear:
        if st.button("🗑 Clear Portfolio", key="port_clear"):
            st.session_state[port_key] = []
            st.rerun()
    with col_ai:
        if st.button("🤖 AI Portfolio Advice", key="port_ai", type="primary",
                      use_container_width=True):
            g     = get_global_stats()
            fg_df = get_fear_greed(1)
            fg_val   = int(fg_df["value"].iloc[-1]) if not fg_df.empty else 50
            btc_dom  = g.get("bitcoin_dominance_percentage", 50)
            mc_chg7  = 0  # approximate

            holdings_for_ai = [
                {"symbol": e["symbol"], "name": e["symbol"],
                 "value_usd": e["value"],
                 "pct_portfolio": e["value"] / max(1, total_value) * 100,
                 "change_7d": e["change_7d"]}
                for e in enriched
            ]
            with st.spinner("Generating portfolio advice…"):
                advice = advise_portfolio(
                    holdings=holdings_for_ai,
                    total_value=total_value,
                    fear_greed=fg_val,
                    btc_dominance=btc_dom,
                    market_change_7d=mc_chg7,
                )
            st.session_state["port_advice"] = advice

    if adv := st.session_state.get("port_advice"):
        st.markdown("#### 🤖 AI Portfolio Advice")
        items = [
            ("Overall Assessment",     adv.get("overall_assessment")),
            ("Concentration Risk",     adv.get("concentration_risk")),
            ("Rebalancing Suggestion", adv.get("rebalancing_suggestion")),
            ("Market Timing",          adv.get("market_timing")),
            ("Top Concern",            adv.get("top_concern")),
            ("Opportunity",            adv.get("opportunity")),
        ]
        for label, text in items:
            if text:
                st.markdown(f"**{label}:** {text}")