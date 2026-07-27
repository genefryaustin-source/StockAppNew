"""
modules/crypto/crypto_sentiment.py

Crypto sentiment & news aggregator — multiple free sources.

Sources (all free, no new keys):
  1. Finnhub         — crypto news feed with sentiment (existing key)
  2. ApeWisdom       — Reddit mentions for crypto (all-crypto filter, no key)
  3. CoinGecko       — community data: Twitter/Reddit/Telegram activity
  4. Polymarket      — prediction market odds on crypto price targets
  5. Blockchain.info — BTC on-chain metrics (hashrate, mempool, fees)
  6. CoinGecko       — derivatives: futures OI, funding rates
"""
from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
import pandas as pd

_CACHE: dict = {}
_TTL = {
    "news":      300,   # 5 min
    "reddit":    600,   # 10 min
    "community": 300,   # 5 min
    "polymarket":900,   # 15 min
    "onchain":   300,   # 5 min
    "derivatives":300,  # 5 min
}

def _get(url, params=None, timeout=8) -> Optional[dict | list]:
    try:
        r = requests.get(
            url,
            params=params or {},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                     "Accept": "application/json"},
            timeout=timeout,
        )
        return r.json() if r.status_code == 200 else None
    except Exception as e:
        print(f"[crypto_sentiment] {url[:50]}: {e}")
        return None

def _cached(key):
    e = _CACHE.get(key)
    ttl_key = key.split("_")[0]
    return e["d"] if e and time.time() - e["t"] < _TTL.get(ttl_key, 300) else None

def _cache(key, d):
    _CACHE[key] = {"d": d, "t": time.time()}
    return d

def _secret(name):
    import os, streamlit as st
    try:
        v = st.secrets.get(name, "")
        if v: return str(v)
    except Exception: pass
    return os.getenv(name, "")


# ── 1. Finnhub Crypto News ─────────────────────────────────────────────────────

def get_crypto_news(coin_symbol: str = None, limit: int = 20) -> list[dict]:
    """
    Crypto news from Finnhub with sentiment scores.
    coin_symbol: optional filter e.g. "BTC", "ETH"
    """
    cache_key = f"news_{coin_symbol}_{limit}"
    cached = _cached(cache_key)
    if cached: return cached

    key = _secret("FINNHUB_API_KEY")
    if not key:
        return []

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news",
            params={"category": "crypto", "token": key},
            timeout=10,
        )
        if r.status_code != 200:
            return []

        items = r.json() or []
        results = []
        for item in items[:limit]:
            headline  = item.get("headline","")
            summary   = item.get("summary","")
            source    = item.get("source","")
            url       = item.get("url","")
            ts        = item.get("datetime",0)
            sentiment = item.get("sentiment","") # positive/negative/neutral if available

            # Filter by coin if specified
            if coin_symbol:
                combined = (headline + summary).upper()
                if coin_symbol.upper() not in combined:
                    continue

            results.append({
                "headline":  headline,
                "summary":   summary[:180] + "…" if len(summary) > 180 else summary,
                "source":    source,
                "url":       url,
                "published": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                             if ts else "",
                "sentiment": sentiment,
            })

        return _cache(cache_key, results[:limit])
    except Exception as e:
        print(f"[crypto_sentiment] Finnhub news error: {e}")
        return []


def get_finnhub_news_sentiment(coin_symbol: str) -> dict:
    """
    News sentiment summary for a specific coin from Finnhub.
    """
    cache_key = f"news_sent_{coin_symbol}"
    cached = _cached(cache_key)
    if cached: return cached

    key = _secret("FINNHUB_API_KEY")
    if not key:
        return {}

    # Map coin symbol to Finnhub format
    sym_map = {
        "BTC":"BINANCE:BTCUSDT","ETH":"BINANCE:ETHUSDT",
        "SOL":"BINANCE:SOLUSDT","BNB":"BINANCE:BNBUSDT",
        "XRP":"BINANCE:XRPUSDT","ADA":"BINANCE:ADAUSDT",
        "DOGE":"BINANCE:DOGEUSDT","AVAX":"BINANCE:AVAXUSDT",
        "DOT":"BINANCE:DOTUSDT","LINK":"BINANCE:LINKUSDT",
    }
    fh_sym = sym_map.get(coin_symbol.upper(), f"BINANCE:{coin_symbol.upper()}USDT")

    try:
        r = requests.get(
            "https://finnhub.io/api/v1/news-sentiment",
            params={"symbol": fh_sym, "token": key},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            result = {
                "buzz_weekly":    data.get("buzz",{}).get("weeklyAverage"),
                "buzz_change":    data.get("buzz",{}).get("increment"),
                "articles_week":  data.get("buzz",{}).get("articlesInLastWeek"),
                "bullish_pct":    data.get("sentiment",{}).get("bullishPercent"),
                "bearish_pct":    data.get("sentiment",{}).get("bearishPercent"),
                "symbol":         coin_symbol.upper(),
                "source":         "finnhub",
            }
            return _cache(cache_key, result)
    except Exception as e:
        print(f"[crypto_sentiment] Finnhub news-sentiment error: {e}")
    return {}


# ── 2. ApeWisdom Reddit Crypto Mentions ───────────────────────────────────────

def get_reddit_crypto_mentions(coin_symbol: str = None) -> list[dict] | dict:
    """
    Reddit mentions for crypto assets via ApeWisdom all-crypto filter.
    No API key required.
    """
    cache_key = f"reddit_{coin_symbol or 'all'}"
    cached = _cached(cache_key)
    if cached: return cached

    data = _get("https://apewisdom.io/api/v1.0/filter/all-crypto/page/1")
    if not data or "results" not in data:
        return [] if not coin_symbol else {}

    results = data.get("results", [])

    if coin_symbol:
        sym = coin_symbol.upper()
        for item in results:
            if str(item.get("ticker","")).upper() == sym or \
               str(item.get("name","")).upper() == sym:
                result = {
                    "symbol":          str(item.get("ticker","")).upper(),
                    "name":            item.get("name",""),
                    "rank":            int(item.get("rank",0)),
                    "mentions":        int(item.get("mentions",0)),
                    "upvotes":         int(item.get("upvotes",0)),
                    "rank_24h_ago":    int(item.get("rank_24h_ago",0)),
                    "mentions_24h_ago":int(item.get("mentions_24h_ago",0)),
                    "rank_change":     int(item.get("rank_24h_ago",0)) - int(item.get("rank",0)),
                    "found":           True,
                }
                return _cache(cache_key, result)
        return {"found": False, "symbol": coin_symbol.upper()}

    # Return full trending list
    trending = []
    for item in results[:25]:
        rc = int(item.get("rank_24h_ago",0)) - int(item.get("rank",0))
        trending.append({
            "symbol":          str(item.get("ticker","")).upper(),
            "name":            item.get("name",""),
            "rank":            int(item.get("rank",0)),
            "mentions":        int(item.get("mentions",0)),
            "upvotes":         int(item.get("upvotes",0)),
            "rank_change":     rc,
            "buzz_trend":      "🔥 Rising" if rc > 3 else "📉 Falling" if rc < -3 else "➡️ Stable",
        })
    return _cache(cache_key, trending)


# ── 3. CoinGecko Community Data ───────────────────────────────────────────────

def get_community_sentiment(coin_detail: dict) -> dict:
    """
    Extract community/social metrics from CoinGecko coin detail response.
    Already fetched in coin_detail — just parse and enrich.
    """
    if not coin_detail:
        return {}

    cd = coin_detail.get("community_data", {})
    md = coin_detail.get("market_data", {})
    dv = coin_detail.get("developer_data", {})
    si = coin_detail.get("sentiment_votes_up_percentage")
    sd = coin_detail.get("sentiment_votes_down_percentage")

    # Sentiment score from community votes
    if si is not None and sd is not None:
        composite = si - sd  # -100 to +100
        label = ("Very Bullish"  if composite > 40 else
                 "Bullish"       if composite > 15 else
                 "Neutral"       if composite > -15 else
                 "Bearish"       if composite > -40 else
                 "Very Bearish")
    else:
        composite = None
        label = "Unknown"

    return {
        "twitter_followers":       cd.get("twitter_followers"),
        "reddit_subscribers":      cd.get("reddit_subscribers"),
        "reddit_posts_48h":        cd.get("reddit_average_posts_48h"),
        "reddit_comments_48h":     cd.get("reddit_average_comments_48h"),
        "reddit_active_48h":       cd.get("reddit_accounts_active_48h"),
        "telegram_users":          cd.get("telegram_channel_user_count"),
        "sentiment_votes_up":      si,
        "sentiment_votes_down":    sd,
        "composite_score":         composite,
        "label":                   label,
        "github_stars":            dv.get("stars"),
        "github_forks":            dv.get("forks"),
        "github_commits_4w":       dv.get("commit_count_4_weeks"),
        "source":                  "coingecko_community",
    }


# ── 4. Polymarket Prediction Market ───────────────────────────────────────────

def get_polymarket_crypto(keywords: list[str] = None) -> list[dict]:
    """
    Fetch crypto-related prediction markets from Polymarket.
    Shows what the market thinks the probability is of crypto price events.
    Free, no key required.
    """
    cache_key = "polymarket_crypto"
    cached = _cached(cache_key)
    if cached: return cached

    keywords = keywords or ["bitcoin","ethereum","crypto","BTC","ETH","solana"]

    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"limit": 100, "closed": "false", "order": "volume24hr",
                    "ascending": "false"},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        if r.status_code != 200:
            return []

        markets = r.json()
        results = []

        for m in markets:
            q = str(m.get("question","")).lower()
            desc = str(m.get("description","")).lower()

            if not any(kw.lower() in q or kw.lower() in desc for kw in keywords):
                continue

            outcomes_str = m.get("outcomes","[]")
            try:
                import json
                outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
            except Exception:
                outcomes = []

            prices_str = m.get("outcomePrices","[]")
            try:
                import json
                prices = json.loads(prices_str) if isinstance(prices_str, str) else prices_str
            except Exception:
                prices = []

            # Build outcome dict
            outcome_probs = {}
            for i, outcome in enumerate(outcomes[:4]):
                prob = float(prices[i]) if i < len(prices) else None
                outcome_probs[outcome] = round(prob * 100, 1) if prob is not None else None

            yes_prob = outcome_probs.get("Yes") or (list(outcome_probs.values())[0] if outcome_probs else None)

            results.append({
                "question":     m.get("question",""),
                "yes_prob":     yes_prob,
                "outcome_probs":outcome_probs,
                "volume":       float(m.get("volume","0") or 0),
                "volume_24h":   float(m.get("volume24hr","0") or 0),
                "end_date":     str(m.get("endDate",""))[:10],
                "url":          f"https://polymarket.com/event/{m.get('slug','')}",
            })

            if len(results) >= 15:
                break

        results.sort(key=lambda x: x["volume_24h"], reverse=True)
        return _cache(cache_key, results[:15])

    except Exception as e:
        print(f"[crypto_sentiment] Polymarket error: {e}")
        return []


# ── 5. Blockchain.com On-Chain Metrics ────────────────────────────────────────

def get_btc_onchain() -> dict:
    """
    Bitcoin on-chain metrics from blockchain.info.
    No API key required. Updates every ~10 minutes.
    """
    cache_key = "onchain_btc"
    cached = _cached(cache_key)
    if cached: return cached

    try:
        # Stats endpoint
        r = requests.get(
            "https://blockchain.info/stats?format=json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=8,
        )
        if r.status_code != 200:
            return {}

        d = r.json()
        result = {
            "hashrate_th":     d.get("hash_rate"),          # TH/s
            "difficulty":      d.get("difficulty"),
            "mempool_size":    d.get("mempool_size"),        # bytes
            "n_unconfirmed":   d.get("n_tx_not_mined"),     # unconfirmed txs
            "total_fees_24h":  d.get("total_fees_btc"),     # BTC
            "n_tx_24h":        d.get("n_tx"),               # transactions in 24h
            "blocks_mined_24h":d.get("n_blocks_mined"),
            "btc_sent_24h":    d.get("total_btc_sent"),     # satoshis
            "market_price":    d.get("market_price_usd"),
            "trade_volume":    d.get("trade_volume_usd"),
            "miners_revenue":  d.get("miners_revenue_usd"),
            "source":          "blockchain.info",
        }
        return _cache(cache_key, result)

    except Exception as e:
        print(f"[crypto_sentiment] Blockchain.info error: {e}")
        return {}


# ── 6. CoinGecko Derivatives (Futures/Funding Rates) ─────────────────────────

def get_derivatives_data() -> list[dict]:
    """
    Futures/perpetual contract data including funding rates and OI.
    """
    cache_key = "derivatives"
    cached = _cached(cache_key)
    if cached: return cached

    try:
        from pycoingecko import CoinGeckoAPI
        cg = CoinGeckoAPI()
        data = cg.get_derivatives(include_tickers="unexpired")
        if not data:
            return []

        rows = []
        seen = set()
        for item in data:
            market  = item.get("market","")
            symbol  = str(item.get("symbol","")).upper()
            # Dedup by symbol + market
            key_dup = f"{market}:{symbol}"
            if key_dup in seen:
                continue
            seen.add(key_dup)

            funding = item.get("funding_rate")
            oi      = item.get("open_interest")
            volume  = item.get("volume_24h")
            price   = item.get("price")

            rows.append({
                "Symbol":       symbol,
                "Exchange":     market,
                "Price":        float(price) if price else None,
                "Volume 24h":   float(volume) if volume else None,
                "Open Interest":float(oi) if oi else None,
                "Funding Rate": float(funding) if funding else None,
                "Basis %":      item.get("basis"),
                "Spread":       item.get("spread"),
                "Expiry":       str(item.get("expired_at",""))[:10] or "Perp",
            })

            if len(rows) >= 50:
                break

        return _cache(cache_key, rows)
    except Exception as e:
        print(f"[crypto_sentiment] Derivatives error: {e}")
        return []


# ── Composite crypto sentiment ─────────────────────────────────────────────────

def get_composite_crypto_sentiment(
    coin_id: str,
    coin_symbol: str,
    coin_detail: dict,
) -> dict:
    """
    Aggregate all sentiment sources into a composite score for a coin.
    """
    community = get_community_sentiment(coin_detail)
    news_sent  = get_finnhub_news_sentiment(coin_symbol)
    reddit     = get_reddit_crypto_mentions(coin_symbol)

    scores  = []
    weights = []
    sources = []

    # CoinGecko community votes (most reliable — direct user sentiment)
    cg_score = community.get("composite_score")
    if cg_score is not None:
        scores.append(cg_score)
        weights.append(0.40)
        sources.append("CoinGecko Community Votes")

    # Finnhub news sentiment
    bull = news_sent.get("bullish_pct")
    bear = news_sent.get("bearish_pct")
    if bull is not None and bear is not None:
        fh_score = bull - bear
        scores.append(fh_score)
        weights.append(0.35)
        sources.append("Finnhub News Sentiment")

    # Reddit rank change (ApeWisdom)
    if isinstance(reddit, dict) and reddit.get("found"):
        rc = reddit.get("rank_change", 0)
        reddit_score = min(50, max(-50, rc * 5))
        scores.append(reddit_score)
        weights.append(0.25)
        sources.append("Reddit Mentions (ApeWisdom)")

    if scores:
        total_w = sum(weights)
        composite = round(sum(s * w for s, w in zip(scores, weights)) / total_w, 1)
    else:
        composite = 0.0

    label = ("Very Bullish"  if composite > 40 else
             "Bullish"       if composite > 15 else
             "Slightly Bullish" if composite > 5 else
             "Neutral"       if composite > -5 else
             "Slightly Bearish" if composite > -15 else
             "Bearish"       if composite > -40 else
             "Very Bearish")

    return {
        "composite_score":  composite,
        "label":            label,
        "sources_used":     sources,
        "community":        community,
        "news_sentiment":   news_sent,
        "reddit":           reddit if isinstance(reddit, dict) else {},
    }