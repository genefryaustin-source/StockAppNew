"""
modules/sentiment/sentiment_ui.py

Social Sentiment — Streamlit UI.

Tabs:
  🎯 Sentiment Score  — composite score + per-source breakdown
  📊 Reddit WSB       — ApeWisdom mentions, rank, buzz trend
  🐦 Twitter/X        — FinTwit sentiment (adanos)
  💬 StockTwits       — live message stream + bull/bear counts
  🔥 Trending Now     — market-wide trending tickers (no symbol needed)

Add to app.py:
    elif page == "Social Sentiment":
        from modules.sentiment.sentiment_ui import render_sentiment_page
        render_sentiment_page(db, user)
"""

from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from modules.sentiment.sentiment_service import (
    get_apewisdom_trending,
    get_composite_sentiment,
    get_trending_tickers,
)


# ─────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────

def render_sentiment_page(db, user: dict):
    st.header("🌐 Social Sentiment")
    st.caption(
        "Retail sentiment aggregated from Reddit WallStreetBets · X/Twitter FinTwit · "
        "StockTwits · News · "
        "Sources: ApeWisdom (free) · adanos.org (free) · StockTwits (public) · Finnhub"
    )

    col_sym, col_ref = st.columns([3, 1])
    with col_sym:
        ticker = st.text_input(
            "Symbol (or leave blank for trending)",
            value="",
            placeholder="NVDA, TSLA, AAPL…",
            key="sent_ticker",
        ).upper().strip()
    with col_ref:
        st.write("")
        if st.button("↺ Refresh", key="sent_refresh", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("sent_cache_"):
                    del st.session_state[k]
            st.rerun()

    if ticker:
        _render_ticker_sentiment(ticker)
    else:
        _render_trending()


# ─────────────────────────────────────────────────────────────
# Ticker sentiment view
# ─────────────────────────────────────────────────────────────

def _render_ticker_sentiment(ticker: str):
    cache_key = f"sent_cache_{ticker}"
    if cache_key not in st.session_state:
        with st.spinner(f"Gathering sentiment for {ticker} from all sources…"):
            st.session_state[cache_key] = get_composite_sentiment(ticker)

    data      = st.session_state[cache_key]
    reddit    = data.get("reddit", {})
    twitter   = data.get("twitter", {})
    st_data   = data.get("stocktwits", {})
    ape       = data.get("apewisdom", {})
    fh        = data.get("finnhub", {})
    composite = data.get("composite_score", 0)
    label     = data.get("label", "Neutral")
    n_sources = data.get("n_sources", 0)

    tab_score, tab_reddit, tab_twitter, tab_twits, tab_news = st.tabs([
        "🎯 Sentiment Score",
        "📊 Reddit",
        "🐦 Twitter/X",
        "💬 StockTwits",
        "📰 News",
    ])

    with tab_score:
        _render_composite(ticker, composite, label, n_sources, data)

    with tab_reddit:
        _render_reddit_tab(ticker, reddit, ape)

    with tab_twitter:
        _render_twitter_tab(ticker, twitter)

    with tab_twits:
        _render_stocktwits_tab(ticker, st_data)

    with tab_news:
        _render_news_tab(ticker, fh)


# ─────────────────────────────────────────────────────────────
# Tab 1 — Composite Score
# ─────────────────────────────────────────────────────────────

def _render_composite(ticker: str, score: float, label: str,
                      n_sources: int, data: dict):
    st.subheader(f"🎯 Composite Sentiment — {ticker}")

    # Colour
    if score > 15:
        color = "#1D9E75"
    elif score < -15:
        color = "#E24B4A"
    else:
        color = "#BA7517"

    st.markdown(
        f"<h2 style='margin:0'>"
        f"<span style='color:{color}'>{label}</span>"
        f"<span style='font-size:16px;color:#8B949E;margin-left:12px'>"
        f"Score: {score:+.0f} / 100</span></h2>",
        unsafe_allow_html=True,
    )
    st.caption(f"Aggregated from {n_sources} source(s): "
               f"{', '.join(data.get('sources_used', []))}")

    # Gauge bar
    _render_sentiment_gauge(score)

    st.divider()

    # Per-source metrics
    st.markdown("#### Per-Source Breakdown")

    reddit  = data.get("reddit", {})
    twitter = data.get("twitter", {})
    st_data = data.get("stocktwits", {})
    ape     = data.get("apewisdom", {})
    fh      = data.get("finnhub", {})

    cols = st.columns(4)

    with cols[0]:
        st.markdown("**Reddit (adanos)**")
        if reddit.get("found"):
            bull = reddit.get("bullish_pct")
            bear = reddit.get("bearish_pct")
            st.metric("Buzz Score", f"{reddit.get('buzz_score', 0):.0f}" if reddit.get("buzz_score") else "—")
            st.metric("Bullish",    f"{bull:.0f}%" if bull is not None else "—")
            st.metric("Bearish",    f"{bear:.0f}%" if bear is not None else "—")
            st.metric("Mentions",   f"{reddit.get('mentions', 0):,}")
            st.caption(f"Trend: {reddit.get('trend', '—')}")
        else:
            st.info("No Reddit data")

    with cols[1]:
        st.markdown("**X/Twitter (adanos)**")
        if twitter.get("found"):
            bull = twitter.get("bullish_pct")
            bear = twitter.get("bearish_pct")
            st.metric("Buzz Score", f"{twitter.get('buzz_score', 0):.0f}" if twitter.get("buzz_score") else "—")
            st.metric("Bullish",    f"{bull:.0f}%" if bull is not None else "—")
            st.metric("Bearish",    f"{bear:.0f}%" if bear is not None else "—")
            st.metric("Mentions",   f"{twitter.get('mentions', 0):,}")
            st.caption(f"Trend: {twitter.get('trend', '—')}")
        else:
            st.info("No Twitter data")

    with cols[2]:
        st.markdown("**StockTwits**")
        if st_data.get("found"):
            st.metric("Sentiment",  st_data.get("sentiment_label", "—"))
            st.metric("Bullish",    f"{st_data.get('bull_pct', 0):.0f}%" if st_data.get("bull_pct") is not None else "—")
            st.metric("Bearish",    f"{st_data.get('bear_pct', 0):.0f}%" if st_data.get("bear_pct") is not None else "—")
            st.metric("Messages",   f"{st_data.get('total_messages', 0):,}")
        else:
            st.info("No StockTwits data")

    with cols[3]:
        st.markdown("**Reddit WSB (ApeWisdom)**")
        if ape.get("found"):
            rc = ape.get("rank_change")
            st.metric("WSB Rank",   f"#{ape.get('rank', '—')}")
            st.metric("Mentions",   f"{ape.get('mentions', 0):,}")
            st.metric("Rank Chg",   f"{rc:+d}" if rc is not None else "—",
                      delta_color="normal" if rc and rc > 0 else "inverse")
            st.metric("Upvotes",    f"{ape.get('upvotes', 0):,}")
        else:
            st.info("Not trending on WSB")

    # Interpretation
    st.divider()
    _render_interpretation(label, score, data)


def _render_sentiment_gauge(score: float):
    """Horizontal bar gauge from -100 to +100."""
    fig, ax = plt.subplots(figsize=(10, 0.8), facecolor="#0F1117")
    ax.set_facecolor("#0F1117")

    # Background gradient
    gradient = [
        (-100, -40, "#E24B4A"),
        (-40,  -10, "#FF8C00"),
        (-10,   10, "#BA7517"),
        ( 10,   40, "#4CAF50"),
        ( 40,  100, "#1D9E75"),
    ]
    for start, end, col in gradient:
        ax.barh(0, end - start, left=start, height=0.5, color=col, alpha=0.35)

    # Score indicator
    ax.axvline(score, color="white", linewidth=3, zorder=5)
    ax.text(score, 0.45, f"{score:+.0f}", ha="center", va="bottom",
            fontsize=10, color="white", fontweight="bold")

    # Labels
    for x, lbl in [(-80, "Very\nBearish"), (-25, "Bearish"), (0, "Neutral"),
                   (25, "Bullish"), (80, "Very\nBullish")]:
        ax.text(x, -0.45, lbl, ha="center", va="top",
                fontsize=6.5, color="#8B949E")

    ax.set_xlim(-100, 100)
    ax.set_ylim(-0.6, 0.7)
    ax.axis("off")
    plt.tight_layout(pad=0)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)


def _render_interpretation(label: str, score: float, data: dict):
    reddit  = data.get("reddit", {})
    ape     = data.get("apewisdom", {})
    st_data = data.get("stocktwits", {})

    if score > 30:
        msg = (
            f"**{label} on {data['ticker']}** — Multiple social sources showing strong retail enthusiasm. "
        )
        if ape.get("found"):
            msg += f"Trending #{ape.get('rank')} on WSB with {ape.get('mentions', 0):,} mentions. "
        if reddit.get("bullish_pct"):
            msg += f"Reddit {reddit['bullish_pct']:.0f}% bullish. "
        msg += "Elevated retail attention can precede short-term momentum but also signals crowded positioning."
        st.success(msg)

    elif score < -30:
        msg = (
            f"**{label} on {data['ticker']}** — Social sentiment broadly negative across sources. "
        )
        if reddit.get("bearish_pct"):
            msg += f"Reddit {reddit['bearish_pct']:.0f}% bearish. "
        msg += "Negative retail sentiment can be contrarian at extremes — institutions often buy when retail sells."
        st.warning(msg)

    else:
        st.info(
            f"**{label}** — Mixed or low social signal. "
            "This is the most common state — most tickers are not trending on social at any given time."
        )


# ─────────────────────────────────────────────────────────────
# Tab 2 — Reddit
# ─────────────────────────────────────────────────────────────

def _render_reddit_tab(ticker: str, reddit: dict, ape: dict):
    st.subheader(f"📊 Reddit Sentiment — {ticker}")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### adanos.org — 50+ Subreddits")
        if reddit.get("found"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Buzz Score",  f"{reddit.get('buzz_score', 0):.1f}" if reddit.get("buzz_score") else "—")
            c2.metric("Bullish %",   f"{reddit.get('bullish_pct', 0):.0f}%" if reddit.get("bullish_pct") is not None else "—")
            c3.metric("Bearish %",   f"{reddit.get('bearish_pct', 0):.0f}%" if reddit.get("bearish_pct") is not None else "—")
            st.metric("Mentions",    f"{reddit.get('mentions', 0):,}")
            st.metric("Trend",       reddit.get("trend", "—"))

            # Bull/bear donut
            bull = reddit.get("bullish_pct") or 0
            bear = reddit.get("bearish_pct") or 0
            if bull + bear > 0:
                _render_bull_bear_donut(bull, bear, "Reddit Sentiment")

            # Top posts
            posts = reddit.get("top_posts", [])
            if posts:
                st.markdown("**Top Posts**")
                for p in posts[:3]:
                    st.markdown(
                        f"- {p.get('text_snippet', p.get('title', ''))[:100]}… "
                        f"👍 {p.get('upvotes', p.get('score', 0))}"
                    )
        else:
            st.info(f"No Reddit data for {ticker} from adanos.org.")
            st.caption("adanos.org covers tickers with meaningful Reddit activity. "
                       "Low-volume tickers may not appear.")

    with col2:
        st.markdown("#### ApeWisdom — WSB Focus")
        if ape.get("found"):
            c1, c2 = st.columns(2)
            c1.metric("WSB Rank",       f"#{ape.get('rank', '—')}")
            c2.metric("24h Rank Chg",   f"{ape.get('rank_change', 0):+d}" if ape.get("rank_change") is not None else "New")
            c1.metric("Mentions Today", f"{ape.get('mentions', 0):,}")
            c2.metric("Yesterday",      f"{ape.get('mentions_24h_ago', 0):,}")
            c1.metric("Upvotes",        f"{ape.get('upvotes', 0):,}")
            trend_icon = {"rising": "📈", "falling": "📉", "stable": "➡️", "new": "🆕"}.get(
                ape.get("buzz_trend", ""), "")
            c2.metric("Buzz Trend",     f"{trend_icon} {ape.get('buzz_trend', '—').title()}")

            if ape.get("rank_change") and ape["rank_change"] > 5:
                st.success(f"🔥 Rapidly rising — rank improved by {ape['rank_change']} positions in 24h")
            elif ape.get("rank_change") and ape["rank_change"] < -5:
                st.warning(f"📉 Fading — rank dropped by {abs(ape['rank_change'])} positions in 24h")
        else:
            st.info(f"{ticker} is not currently trending in the top Reddit mentions.")
            st.caption("ApeWisdom tracks the top ~800 tickers by Reddit activity. "
                       "Most tickers aren't trending at any given time.")


# ─────────────────────────────────────────────────────────────
# Tab 3 — Twitter/X
# ─────────────────────────────────────────────────────────────

def _render_twitter_tab(ticker: str, twitter: dict):
    st.subheader(f"🐦 X/Twitter (FinTwit) — {ticker}")
    st.caption("Powered by adanos.org · FinTwit = Finance Twitter, a community of retail traders")

    if not twitter.get("found"):
        st.info(
            f"No X/Twitter sentiment data for {ticker}. "
            "adanos.org free tier covers the most-discussed tickers on FinTwit."
        )
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Buzz Score",   f"{twitter.get('buzz_score', 0):.1f}" if twitter.get("buzz_score") else "—")
    c2.metric("Bullish %",    f"{twitter.get('bullish_pct', 0):.0f}%" if twitter.get("bullish_pct") is not None else "—")
    c3.metric("Bearish %",    f"{twitter.get('bearish_pct', 0):.0f}%" if twitter.get("bearish_pct") is not None else "—")
    c4.metric("Mentions",     f"{twitter.get('mentions', 0):,}")

    bull = twitter.get("bullish_pct") or 0
    bear = twitter.get("bearish_pct") or 0
    if bull + bear > 0:
        col_chart, col_info = st.columns([1, 2])
        with col_chart:
            _render_bull_bear_donut(bull, bear, "FinTwit Sentiment")
        with col_info:
            trend = twitter.get("trend", "")
            if trend:
                st.metric("Trend", trend)
            sentiment_score = twitter.get("sentiment_score")
            if sentiment_score is not None:
                st.metric("Sentiment Score",
                          f"{sentiment_score:+.2f}",
                          help="-1 = very bearish, +1 = very bullish")

    tweets = twitter.get("top_tweets", [])
    if tweets:
        st.markdown("**Top FinTwit Posts**")
        for t in tweets[:3]:
            likes    = t.get("likes", 0)
            retweets = t.get("retweets", 0)
            sent     = t.get("sentiment_label", "")
            sent_icon= {"positive": "🟢", "negative": "🔴", "neutral": "⚪"}.get(sent, "")
            st.markdown(
                f"{sent_icon} *{t.get('text_snippet', '')[:120]}…* "
                f"❤️ {likes:,} 🔁 {retweets:,}"
            )


# ─────────────────────────────────────────────────────────────
# Tab 4 — StockTwits
# ─────────────────────────────────────────────────────────────

def _render_stocktwits_tab(ticker: str, st_data: dict):
    st.subheader(f"💬 StockTwits — {ticker}")
    st.caption("Live message stream from StockTwits · Public data, no API key required")

    if not st_data.get("found"):
        st.info(f"No StockTwits messages found for {ticker}.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sentiment",  st_data.get("sentiment_label", "—"))
    c2.metric("Bullish",    st_data.get("bullish", 0))
    c3.metric("Bearish",    st_data.get("bearish", 0))
    c4.metric("Messages",   st_data.get("total_messages", 0))

    bull = st_data.get("bull_pct")
    bear = st_data.get("bear_pct")
    if bull is not None:
        col_donut, col_note = st.columns([1, 2])
        with col_donut:
            _render_bull_bear_donut(bull, bear or 0, "StockTwits")
        with col_note:
            st.caption(
                "StockTwits users can tag messages 🐂 Bullish or 🐻 Bearish. "
                "The ratio of tagged messages is a direct retail sentiment signal. "
                "Untagged messages are excluded from the ratio."
            )

    messages = st_data.get("messages", [])
    if messages:
        st.markdown("**Recent Messages**")
        for msg in messages[:8]:
            icon = {"bullish": "🟢", "bearish": "🔴"}.get(msg.get("sentiment", ""), "⚪")
            likes = msg.get("likes", 0)
            user  = msg.get("user", "")
            body  = msg.get("body", "")[:120]
            st.markdown(f"{icon} **@{user}** — {body}  👍 {likes}")


# ─────────────────────────────────────────────────────────────
# Tab 5 — News sentiment (Finnhub)
# ─────────────────────────────────────────────────────────────

def _render_news_tab(ticker: str, fh: dict):
    st.subheader(f"📰 News Sentiment — {ticker}")
    st.caption("Powered by Finnhub · News article buzz and sentiment scoring")

    if not fh.get("found"):
        st.info("No Finnhub news sentiment data available.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("News Buzz",      f"{fh.get('buzz_weekly', 0):.2f}" if fh.get("buzz_weekly") else "—",
              help="Articles per week vs baseline")
    c2.metric("Buzz Change",    f"{fh.get('buzz_change', 0):+.0f}%" if fh.get("buzz_change") else "—")
    c3.metric("Articles/Week",  fh.get("article_mentions", "—"))
    bull = fh.get("news_sentiment_bullish")
    bear = fh.get("news_sentiment_bearish")
    c4.metric("News Bullish %", f"{bull:.0f}%" if bull is not None else "—")

    if bull is not None and bear is not None:
        _render_bull_bear_donut(bull, bear, "News Sentiment")

    # Social scores from Finnhub if available
    reddit_score  = fh.get("social_reddit_score")
    twitter_score = fh.get("social_twitter_score")
    if reddit_score or twitter_score:
        st.markdown("**Finnhub Social Scores**")
        sc1, sc2 = st.columns(2)
        if reddit_score is not None:
            sc1.metric("Reddit Score",   f"{reddit_score:+.3f}",
                       help="Finnhub Reddit sentiment score (-1 bearish → +1 bullish)")
            sc1.metric("Reddit Mentions",fh.get("social_reddit_mentions", 0))
        if twitter_score is not None:
            sc2.metric("Twitter Score",  f"{twitter_score:+.3f}")
            sc2.metric("Twitter Mentions",fh.get("social_twitter_mentions", 0))


# ─────────────────────────────────────────────────────────────
# Trending view (no ticker)
# ─────────────────────────────────────────────────────────────

def _render_trending():
    st.subheader("🔥 Trending Tickers — Reddit & Social")
    st.caption("Most mentioned tickers across Reddit WallStreetBets and finance subreddits right now")

    cache_key = "sent_cache_trending"
    if cache_key not in st.session_state:
        with st.spinner("Loading trending tickers…"):
            st.session_state[cache_key] = get_trending_tickers()

    trending = st.session_state[cache_key]
    ape_data = trending.get("reddit_wsb", [])

    tab_wsb, tab_broad = st.tabs(["📊 Reddit WSB (ApeWisdom)", "🌐 All Reddit (adanos)"])

    with tab_wsb:
        if not ape_data:
            st.info("ApeWisdom data unavailable — may be rate limited.")
            return

        st.markdown(f"**Top {len(ape_data)} tickers on r/WallStreetBets right now**")

        rows = []
        for item in ape_data:
            rc = item.get("rank_change", 0)
            trend_icon = "🔥" if rc > 10 else "📈" if rc > 0 else "📉" if rc < 0 else "➡️"
            rows.append({
                "Rank":        item["rank"],
                "Ticker":      item["ticker"],
                "Name":        item.get("name", "")[:25],
                "Mentions":    f"{item['mentions']:,}",
                "Upvotes":     f"{item.get('upvotes', 0):,}",
                "Yesterday":   f"#{item.get('rank_24h_ago', '—')}",
                "Trend":       f"{trend_icon} {item.get('buzz_trend', '').title()}",
            })

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        # Rank change chart
        if len(ape_data) >= 5:
            _render_rank_change_chart(ape_data[:15])

    with tab_broad:
        adanos_data = trending.get("reddit_all", [])
        if not adanos_data:
            st.info("adanos.org trending data unavailable.")
            st.caption("Type a specific ticker above to check its sentiment.")
            return

        rows2 = []
        for item in adanos_data:
            rows2.append({
                "Ticker":      item.get("ticker", ""),
                "Buzz Score":  f"{item.get('buzz_score', 0):.1f}" if item.get("buzz_score") else "—",
                "Bullish %":   f"{item.get('bullish_pct', 0):.0f}%" if item.get("bullish_pct") else "—",
                "Mentions":    f"{item.get('mentions', 0):,}",
                "Trend":       item.get("trend", ""),
            })

        st.dataframe(pd.DataFrame(rows2), use_container_width=True, hide_index=True)


def _render_rank_change_chart(ape_data: list):
    tickers   = [d["ticker"] for d in ape_data]
    rank_now  = [d["rank"] for d in ape_data]
    rank_prev = [d.get("rank_24h_ago") or d["rank"] for d in ape_data]
    changes   = [p - n for p, n in zip(rank_prev, rank_now)]
    colors    = ["#1D9E75" if c > 0 else "#E24B4A" if c < 0 else "#8B949E" for c in changes]

    fig, ax = plt.subplots(figsize=(10, 3), facecolor="#0F1117")
    ax.set_facecolor("#161B22")
    ax.bar(range(len(tickers)), changes, color=colors, alpha=0.85)
    ax.axhline(0, color="#30363D", linewidth=0.8)
    ax.set_xticks(range(len(tickers)))
    ax.set_xticklabels(tickers, rotation=45, ha="right", fontsize=8, color="#8B949E")
    ax.set_ylabel("Rank Change (↑ = more popular)", color="#8B949E", fontsize=8)
    ax.set_title("Reddit WSB Rank Change vs Yesterday", color="#C9D1D9", fontsize=10)
    ax.tick_params(colors="#8B949E")
    ax.spines[:].set_color("#21262D")
    ax.grid(axis="y", color="#21262D", linewidth=0.3, alpha=0.4)
    plt.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Shared chart — bull/bear donut
# ─────────────────────────────────────────────────────────────

def _render_bull_bear_donut(bull: float, bear: float, title: str = ""):
    neutral = max(0, 100 - bull - bear)
    sizes   = []
    colors  = []
    labels  = []

    if bull > 0:
        sizes.append(bull);   colors.append("#1D9E75"); labels.append(f"Bull {bull:.0f}%")
    if bear > 0:
        sizes.append(bear);   colors.append("#E24B4A"); labels.append(f"Bear {bear:.0f}%")
    if neutral > 0:
        sizes.append(neutral);colors.append("#4A5568"); labels.append(f"Neutral {neutral:.0f}%")

    if not sizes:
        return

    fig, ax = plt.subplots(figsize=(3, 3), facecolor="#0F1117")
    ax.set_facecolor("#0F1117")
    wedges, _, autotexts = ax.pie(
        sizes, autopct="%1.0f%%", colors=colors,
        startangle=90, wedgeprops={"linewidth": 2, "edgecolor": "#0F1117"},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(9)
    circle = plt.Circle((0, 0), 0.55, fc="#0F1117")
    ax.add_artist(circle)
    sentiment = "🐂" if bull > bear else "🐻" if bear > bull else "⚖️"
    ax.text(0, 0, sentiment, ha="center", va="center", fontsize=16)
    if title:
        ax.set_title(title, color="white", fontsize=9)
    ax.legend(labels, loc="lower center", fontsize=7,
              facecolor="#0F1117", labelcolor="white",
              framealpha=0.2, ncol=len(sizes),
              bbox_to_anchor=(0.5, -0.15))
    plt.tight_layout()
    st.pyplot(fig, use_container_width=False)
    plt.close(fig)


# ─────────────────────────────────────────────────────────────
# Embeddable card for Stock Dashboard
# ─────────────────────────────────────────────────────────────

def render_sentiment_card(ticker: str):
    """Compact sentiment card for embedding in Stock Dashboard."""
    try:
        from modules.sentiment.sentiment_service import get_composite_sentiment
        data  = get_composite_sentiment(ticker)
        score = data.get("composite_score", 0)
        label = data.get("label", "Neutral")
    except Exception:
        st.caption("Sentiment data unavailable.")
        return

    color = "#1D9E75" if score > 15 else "#E24B4A" if score < -15 else "#BA7517"
    st.markdown(
        f"**Social Sentiment:** <span style='color:{color}'>{label}</span> "
        f"({score:+.0f})",
        unsafe_allow_html=True,
    )
    ape = data.get("apewisdom", {})
    if ape.get("found"):
        st.caption(
            f"WSB Rank #{ape.get('rank')} · "
            f"{ape.get('mentions', 0):,} mentions · "
            f"{ape.get('buzz_trend', '').title()}"
        )