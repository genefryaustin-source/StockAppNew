"""
modules/crypto/service.py — entry point, imports crypto_service + builds full UI
"""
from modules.crypto.data_service import (
    get_top_coins, get_coin_detail, get_coin_history,
    get_global_stats, get_trending, get_fear_greed,
    get_defi_protocols, search_coin, CATEGORIES, COIN_SYMBOLS,
)
from modules.crypto.crypto_sentiment import (
    get_crypto_news, get_reddit_crypto_mentions, get_community_sentiment,
    get_polymarket_crypto, get_btc_onchain, get_derivatives_data,
    get_composite_crypto_sentiment, get_finnhub_news_sentiment,
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
        "🌡️ Sentiment & News",
        "🤖 AI Analysis",
        "📈 Portfolio Tracker",
    ])

    with tabs[0]: _render_market_overview()
    with tabs[1]: _render_coin_detail()
    with tabs[2]: _render_defi()
    with tabs[3]: _render_sentiment_news()
    with tabs[4]: _render_ai_analysis()
    with tabs[5]: _render_portfolio_tracker()


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
# TAB 3 — SENTIMENT & NEWS
# ══════════════════════════════════════════════════════════════════════════════

def _render_sentiment_news():
    st.subheader("🌡️ Crypto Sentiment & News")
    st.caption(
        "Finnhub crypto news · Reddit mentions (ApeWisdom) · "
        "CoinGecko community votes · Polymarket odds · "
        "BTC on-chain metrics · Futures funding rates"
    )

    subtabs = st.tabs([
        "📰 News Feed",
        "📊 Reddit Buzz",
        "🎲 Polymarket Odds",
        "⛓️ BTC On-Chain",
        "📉 Futures / Funding",
        "🏅 Coin Sentiment",
    ])

    with subtabs[0]: _render_news_feed()
    with subtabs[1]: _render_reddit_crypto()
    with subtabs[2]: _render_polymarket()
    with subtabs[3]: _render_onchain()
    with subtabs[4]: _render_futures()
    with subtabs[5]: _render_coin_sentiment_tab()


def _render_news_feed():
    st.markdown("#### 📰 Crypto News Feed")
    st.caption("Live crypto news from Finnhub with sentiment context")

    col_coin, col_lim = st.columns([2, 1])
    with col_coin:
        filter_coin = st.text_input(
            "Filter by coin (optional)", placeholder="BTC, ETH…",
            key="news_filter_coin",
        ).upper().strip()
    with col_lim:
        limit = st.selectbox("Articles", [10, 20, 50], key="news_limit")

    cache_key = f"crypto_news_{filter_coin}_{limit}"
    if cache_key not in st.session_state or st.button("↺ Refresh", key="news_refresh"):
        with st.spinner("Loading crypto news…"):
            st.session_state[cache_key] = get_crypto_news(
                filter_coin or None, limit
            )

    news = st.session_state.get(cache_key, [])
    if not news:
        st.info("No news articles found. Check your FINNHUB_API_KEY in secrets.")
        return

    for item in news:
        sent = item.get("sentiment","")
        sent_icon = {"positive":"🟢","negative":"🔴","neutral":"⚪"}.get(sent,"📰")
        col_icon, col_body = st.columns([1, 15])
        with col_icon:
            st.markdown(f"### {sent_icon}")
        with col_body:
            st.markdown(f"**{item['headline']}**")
            if item.get("summary"):
                st.caption(item["summary"])
            st.caption(
                f"📡 {item['source']}  ·  🕐 {item['published']}"
                + (f"  ·  [Read →]({item['url']})" if item.get("url") else "")
            )
        st.markdown("---")


def _render_reddit_crypto():
    st.markdown("#### 📊 Reddit Crypto Buzz")
    st.caption("Most mentioned crypto assets on Reddit right now · ApeWisdom (free, no key)")

    cache_key = "reddit_crypto_trending"
    if cache_key not in st.session_state or st.button("↺ Refresh", key="reddit_refresh"):
        with st.spinner("Loading Reddit crypto mentions…"):
            st.session_state[cache_key] = get_reddit_crypto_mentions()

    data = st.session_state.get(cache_key, [])
    if not data or not isinstance(data, list):
        st.info("Reddit data unavailable (may be rate-limited). Try refreshing.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Tracked Coins", len(data))
    top = data[0] if data else {}
    c2.metric("#1 Trending", top.get("symbol","—"), f"{top.get('mentions',0):,} mentions")
    rising = [d for d in data if d.get("rank_change",0) > 3]
    c3.metric("Rising Fast 🔥", len(rising))

    rows = []
    for item in data:
        rows.append({
            "Rank":     item["rank"],
            "Symbol":   item["symbol"],
            "Name":     item.get("name",""),
            "Mentions": f"{item['mentions']:,}",
            "Upvotes":  f"{item.get('upvotes',0):,}",
            "Trend":    item.get("buzz_trend",""),
            "Rank Chg": f"{item.get('rank_change',0):+d}",
        })

    df = pd.DataFrame(rows)
    def _rc_color(v):
        try:
            return f"color: {GREEN}" if int(str(v).replace("+","")) > 0                    else f"color: {RED}" if int(str(v).replace("+","")) < 0 else ""
        except: return ""
    styled = df.style.applymap(_rc_color, subset=["Rank Chg"])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=450)

    if PLOTLY and len(data) >= 5:
        top10 = data[:10]
        fig = go.Figure(go.Bar(
            x=[d["symbol"] for d in top10],
            y=[d["mentions"] for d in top10],
            marker_color=[CALL_CLR if d.get("rank_change",0) >= 0 else RED for d in top10],
            text=[d.get("buzz_trend","") for d in top10],
            textposition="outside",
        ))
        fig.update_layout(
            title="Top 10 Crypto Reddit Mentions",
            template="plotly_dark", paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
            height=300, margin=dict(l=0,r=0,t=40,b=20),
        )
        st.plotly_chart(fig, use_container_width=True)


def _render_polymarket():
    st.markdown("#### 🎲 Polymarket Prediction Markets")
    st.caption(
        "Real-money prediction markets on crypto outcomes. "
        "Probability = what traders bet will happen. Free, no key."
    )

    cache_key = "polymarket_crypto"
    if cache_key not in st.session_state or st.button("↺ Load Markets", key="pm_refresh",
                                                        type="primary"):
        with st.spinner("Loading Polymarket crypto markets…"):
            st.session_state[cache_key] = get_polymarket_crypto()

    markets = st.session_state.get(cache_key, [])
    if not markets:
        st.info("No crypto prediction markets found or Polymarket is unavailable.")
        return

    st.caption(f"{len(markets)} active crypto markets sorted by 24h volume")

    for m in markets:
        yes_prob = m.get("yes_prob")
        vol_24h  = m.get("volume_24h", 0)
        end_date = m.get("end_date","")

        col_q, col_p, col_v = st.columns([4, 1, 1])
        with col_q:
            st.markdown(f"**{m['question']}**")
            if end_date:
                st.caption(f"Closes: {end_date}")
        with col_p:
            if yes_prob is not None:
                color = GREEN if yes_prob > 60 else RED if yes_prob < 40 else "#BA7517"
                st.markdown(
                    f"<h3 style='color:{color};margin:0'>{yes_prob:.0f}%</h3>"
                    f"<p style='color:#8B949E;margin:0;font-size:11px'>YES prob</p>",
                    unsafe_allow_html=True,
                )
        with col_v:
            if vol_24h:
                st.markdown(
                    f"<p style='margin:4px 0;font-size:12px'>${vol_24h:,.0f}</p>"
                    f"<p style='color:#8B949E;margin:0;font-size:11px'>24h vol</p>",
                    unsafe_allow_html=True,
                )
        st.markdown("---")


def _render_onchain():
    st.markdown("#### ⛓️ Bitcoin On-Chain Metrics")
    st.caption("Live BTC network stats from blockchain.info · No key required")

    cache_key = "btc_onchain"
    if cache_key not in st.session_state or st.button("↺ Refresh", key="oc_refresh"):
        with st.spinner("Loading BTC on-chain data…"):
            st.session_state[cache_key] = get_btc_onchain()

    d = st.session_state.get(cache_key, {})
    if not d:
        st.info("On-chain data unavailable.")
        return

    c1,c2,c3,c4 = st.columns(4)
    hr = d.get("hashrate_th")
    c1.metric("Hash Rate",
              f"{hr/1e6:.1f} EH/s" if hr and hr > 1e6 else
              f"{hr/1e3:.0f} PH/s" if hr else "—")
    diff = d.get("difficulty")
    c2.metric("Difficulty",  f"{diff/1e12:.2f}T" if diff else "—")
    nc = d.get("n_unconfirmed")
    c3.metric("Unconfirmed Txs", f"{nc:,}" if nc else "—")
    c4.metric("Blocks (24h)", d.get("blocks_mined_24h","—"))

    c5,c6,c7,c8 = st.columns(4)
    tx24 = d.get("n_tx_24h")
    c5.metric("Transactions (24h)", f"{tx24:,}" if tx24 else "—")
    fees = d.get("total_fees_24h")
    c6.metric("Total Fees (24h)", f"{fees:.2f} BTC" if fees else "—")
    rev = d.get("miners_revenue")
    c7.metric("Miner Revenue", f"${rev:,.0f}" if rev else "—")
    tvol = d.get("trade_volume")
    c8.metric("Trade Volume", f"${tvol:,.0f}" if tvol else "—")


def _render_futures():
    st.markdown("#### 📉 Futures & Funding Rates")
    st.caption(
        "Perpetual contract funding rates and open interest from CoinGecko derivatives. "
        "Negative funding = bears paying bulls (bearish sentiment)."
    )

    cache_key = "crypto_derivatives"
    if cache_key not in st.session_state or st.button("↺ Refresh", key="deriv_refresh"):
        with st.spinner("Loading derivatives data…"):
            st.session_state[cache_key] = get_derivatives_data()

    data = st.session_state.get(cache_key, [])
    if not data:
        st.info("Derivatives data unavailable.")
        return

    df = pd.DataFrame(data)

    # Summary
    if "Funding Rate" in df.columns:
        with_funding = df.dropna(subset=["Funding Rate"])
        if not with_funding.empty:
            avg_funding = with_funding["Funding Rate"].mean()
            positive_funding = (with_funding["Funding Rate"] > 0).sum()
            c1,c2,c3 = st.columns(3)
            c1.metric("Avg Funding Rate", f"{avg_funding*100:.4f}%",
                      help="Positive = longs pay shorts (bullish), Negative = shorts pay longs (bearish)")
            c2.metric("Bullish Contracts", f"{positive_funding}/{len(with_funding)}",
                      delta_color="normal" if positive_funding > len(with_funding)/2 else "inverse")
            c3.metric("Contracts Tracked", len(df))

    # Format
    fmt_df = df.copy()
    for col in ["Price", "Volume 24h", "Open Interest"]:
        if col in fmt_df.columns:
            fmt_df[col] = fmt_df[col].apply(
                lambda v: f"${v:,.2f}" if isinstance(v,(int,float)) and v else "—"
            )
    if "Funding Rate" in fmt_df.columns:
        fmt_df["Funding Rate"] = fmt_df["Funding Rate"].apply(
            lambda v: f"{v*100:+.4f}%" if isinstance(v,(int,float)) else "—"
        )

    def _fr_color(v):
        try:
            val = float(str(v).replace("%","").replace("+",""))
            return f"color: {GREEN}" if val > 0 else f"color: {RED}" if val < 0 else ""
        except: return ""

    show_cols = [c for c in ["Symbol","Exchange","Price","Volume 24h",
                              "Open Interest","Funding Rate","Expiry"]
                 if c in fmt_df.columns]
    styled = fmt_df[show_cols].style.applymap(_fr_color, subset=["Funding Rate"] if "Funding Rate" in show_cols else [])
    st.dataframe(styled, use_container_width=True, hide_index=True, height=400)


def _render_coin_sentiment_tab():
    st.markdown("#### 🏅 Coin-Specific Sentiment Score")
    st.caption(
        "Composite sentiment from CoinGecko community votes + "
        "Finnhub news sentiment + Reddit mentions"
    )

    coin_input = st.text_input(
        "Coin", value="bitcoin", key="sent_coin",
        placeholder="bitcoin, ETH, solana…"
    )
    if not coin_input:
        return

    # Resolve coin ID
    from modules.crypto.data_service import COIN_SYMBOLS, search_coin
    sym_to_id = {v.lower(): k for k, v in COIN_SYMBOLS.items()}
    coin_id = coin_input.lower().strip()
    if coin_id.upper() in {v.upper() for v in COIN_SYMBOLS.values()}:
        coin_id = sym_to_id.get(coin_id.lower(), coin_id)
    symbol = COIN_SYMBOLS.get(coin_id, coin_input.upper())

    if st.button("Load Sentiment", key="sent_load", type="primary"):
        with st.spinner(f"Aggregating sentiment for {symbol}…"):
            from modules.crypto.data_service import get_coin_detail
            detail = get_coin_detail(coin_id)
            result = get_composite_crypto_sentiment(coin_id, symbol, detail)
        st.session_state[f"coin_sent_{coin_id}"] = result

    result = st.session_state.get(f"coin_sent_{coin_id}")
    if not result:
        return

    score = result.get("composite_score", 0)
    label = result.get("label","—")
    color = GREEN if score > 15 else RED if score < -15 else "#BA7517"

    st.markdown(
        f"<h2 style='color:{color}'>{label}"
        f"<span style='font-size:16px;color:#8B949E;margin-left:12px'>"
        f"Score: {score:+.0f} / 100</span></h2>",
        unsafe_allow_html=True,
    )
    st.caption(f"Sources: {', '.join(result.get('sources_used',[]))}")

    # Community data
    comm = result.get("community", {})
    if comm:
        st.markdown("**Community Activity**")
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Twitter Followers",
                  f"{comm.get('twitter_followers',0):,}" if comm.get("twitter_followers") else "—")
        c2.metric("Reddit Subscribers",
                  f"{comm.get('reddit_subscribers',0):,}" if comm.get("reddit_subscribers") else "—")
        c3.metric("Telegram Users",
                  f"{comm.get('telegram_users',0):,}" if comm.get("telegram_users") else "—")
        c4.metric("GitHub Commits (4w)",
                  f"{comm.get('github_commits_4w',0):,}" if comm.get("github_commits_4w") else "—")

        up = comm.get("sentiment_votes_up")
        down = comm.get("sentiment_votes_down")
        if up is not None and down is not None:
            st.markdown(
                f"**CoinGecko Community Vote:** "
                f"🟢 {up:.0f}% Bullish  ·  🔴 {down:.0f}% Bearish"
            )

    # News sentiment
    news = result.get("news_sentiment", {})
    if news.get("bullish_pct") is not None:
        st.markdown("**News Sentiment (Finnhub)**")
        c1,c2,c3 = st.columns(3)
        c1.metric("Bullish News",    f"{news['bullish_pct']:.0f}%")
        c2.metric("Bearish News",    f"{news['bearish_pct']:.0f}%")
        c3.metric("Articles/Week",   news.get("articles_week","—"))

    # Reddit
    reddit = result.get("reddit", {})
    if reddit.get("found"):
        st.markdown("**Reddit Activity (ApeWisdom)**")
        c1,c2,c3 = st.columns(3)
        c1.metric("WSB-Crypto Rank", f"#{reddit.get('rank','—')}")
        c2.metric("Mentions",        f"{reddit.get('mentions',0):,}")
        rc = reddit.get("rank_change",0)
        c3.metric("Rank Change",     f"{rc:+d}", delta_color="normal" if rc > 0 else "inverse")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — DeFi & NFT
# ══════════════════════════════════════════════════════════════════════════════
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
        df = get_top_coins(50)

        btc_ch24 = float(btc_row["24h %"].iloc[0]) if not btc_row.empty and btc_row["24h %"].iloc[0] is not None else 0

        with st.spinner("AI analyzing risks…"):
            alerts = scan_crypto_risks(
                watchlist_coins=df.to_dict("records") if not df.empty else [],
                fear_greed=fg_val,
                btc_change_24h=btc_ch24,
                market_cap_change=mc_chg,
            )
        st.session_state["crypto_risks"] = alerts

    risk_report = st.session_state.get("crypto_risks")

    if risk_report:
        st.markdown(risk_report)


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