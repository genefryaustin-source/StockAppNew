"""
modules/sentiment/sentiment_service.py

Social Sentiment Aggregator — Multi-source retail sentiment.

Sources (all free, no new keys needed):
  ApeWisdom  — Reddit WSB/stocks mentions, no auth
  adanos.org — Reddit + X/Twitter buzz/sentiment, no auth free tier
  StockTwits — Public stream, no auth
  Finnhub    — News sentiment + social sentiment (existing key)

Architecture:
  Each source is independent. If one fails/rate limits, others still work.
  Results are normalised into a common schema and aggregated into a
  composite sentiment score per ticker.

Composite score: -100 (strong bearish) → +100 (strong bullish)
  Weighted: adanos 40%, StockTwits 30%, ApeWisdom buzz 20%, Finnhub 10%
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
import streamlit as st

_CACHE: dict = {}
_CACHE_TTL  = 900   # 15 minutes for social data


# ─────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────

def _get_secret(key: str) -> Optional[str]:
    try:
        if key in st.secrets:
            return str(st.secrets[key]) or None
    except Exception:
        pass
    val = os.getenv(key, "")
    if val:
        return val
    try:
        from modules.utils.config import get_secret
        return get_secret(key) or None
    except Exception:
        pass
    return None


def _get_cached(key: str):
    entry = _CACHE.get(key)
    if entry and time.time() - entry["ts"] < _CACHE_TTL:
        return entry["data"]
    return None


def _set_cached(key: str, data):
    _CACHE[key] = {"data": data, "ts": time.time()}


def _get(url: str, params: dict = None, headers: dict = None, timeout: int = 8) -> Optional[dict]:
    try:
        r = requests.get(
            url,
            params=params or {},
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Accept":     "application/json",
                **(headers or {}),
            },
            timeout=timeout,
        )
        if r.status_code == 200:
            return r.json()
        return {"_status": r.status_code, "_error": r.text[:100]}
    except Exception as e:
        return {"_error": str(e)}


def _sf(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Source 1 — ApeWisdom (Reddit, free, no auth)
# ─────────────────────────────────────────────────────────────

def get_apewisdom(ticker: str) -> dict:
    """
    Reddit mention data from ApeWisdom.
    Scans r/wallstreetbets, r/stocks, r/options, r/investing + others.
    Returns rank, mentions, upvotes, and rank change vs 24h ago.
    No API key required.
    """
    cache_key = f"ape_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    ticker_upper = ticker.upper()

    # Search across pages for this specific ticker
    for page in range(1, 6):
        data = _get(
            f"https://apewisdom.io/api/v1.0/filter/all-stocks/page/{page}"
        )
        if not data or "_error" in data:
            break

        for item in data.get("results", []):
            if str(item.get("ticker", "")).upper() == ticker_upper:
                result = {
                    "source":          "apewisdom",
                    "ticker":          ticker_upper,
                    "rank":            int(item.get("rank") or 0),
                    "mentions":        int(item.get("mentions") or 0),
                    "upvotes":         int(item.get("upvotes") or 0),
                    "rank_24h_ago":    int(item.get("rank_24h_ago") or 0),
                    "mentions_24h_ago":int(item.get("mentions_24h_ago") or 0),
                    "rank_change":     None,
                    "mentions_change": None,
                    "buzz_trend":      "neutral",
                    "found":           True,
                }
                # Compute rank change (lower rank = more popular)
                if result["rank"] and result["rank_24h_ago"]:
                    result["rank_change"] = result["rank_24h_ago"] - result["rank"]
                    result["buzz_trend"] = (
                        "rising"   if result["rank_change"] > 0 else
                        "falling"  if result["rank_change"] < 0 else
                        "stable"
                    )
                if result["mentions_24h_ago"]:
                    result["mentions_change"] = (
                        result["mentions"] - result["mentions_24h_ago"]
                    )
                _set_cached(cache_key, result)
                return result

    # Not found in top results
    result = {
        "source":   "apewisdom",
        "ticker":   ticker_upper,
        "found":    False,
        "rank":     None,
        "mentions": 0,
        "upvotes":  0,
        "buzz_trend": "neutral",
        "note":     "Not in top Reddit mentions currently",
    }
    _set_cached(cache_key, result)
    return result


def get_apewisdom_trending(limit: int = 25) -> list[dict]:
    """
    Get the current top trending tickers on Reddit (market-wide).
    Useful for a trending stocks widget.
    """
    cache_key = "ape_trending"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _get("https://apewisdom.io/api/v1.0/filter/all-stocks/page/1")
    if not data or "_error" in data:
        return []

    results = []
    for item in data.get("results", [])[:limit]:
        rank_now  = int(item.get("rank") or 0)
        rank_prev = int(item.get("rank_24h_ago") or 0)
        results.append({
            "rank":             rank_now,
            "ticker":           str(item.get("ticker", "")).upper(),
            "name":             str(item.get("name", "")),
            "mentions":         int(item.get("mentions") or 0),
            "upvotes":          int(item.get("upvotes") or 0),
            "rank_24h_ago":     rank_prev,
            "mentions_24h_ago": int(item.get("mentions_24h_ago") or 0),
            "rank_change":      rank_prev - rank_now if rank_prev else 0,
            "buzz_trend":       "rising" if rank_prev > rank_now else
                                "falling" if rank_prev and rank_prev < rank_now else "new",
        })

    _set_cached(cache_key, results)
    return results


# ─────────────────────────────────────────────────────────────
# Source 2 — adanos.org (Reddit + X, free tier, no auth)
# ─────────────────────────────────────────────────────────────

def get_adanos_reddit(ticker: str) -> dict:
    """
    Reddit sentiment from adanos.org — buzz score, bullish/bearish %,
    daily trend, top posts. No API key required on free tier.
    """
    cache_key = f"adanos_reddit_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _get(f"https://api.adanos.org/reddit/ticker/{ticker.upper()}")

    if not data or "_error" in data or data.get("found") is False:
        result = {
            "source":       "adanos_reddit",
            "ticker":       ticker.upper(),
            "found":        False,
            "buzz_score":   None,
            "sentiment":    None,
            "bullish_pct":  None,
            "bearish_pct":  None,
        }
        _set_cached(cache_key, result)
        return result

    result = {
        "source":         "adanos_reddit",
        "ticker":         ticker.upper(),
        "found":          True,
        "buzz_score":     _sf(data.get("buzz_score")),
        "sentiment_score":_sf(data.get("sentiment_score")),
        "bullish_pct":    _sf(data.get("bullish_pct")),
        "bearish_pct":    _sf(data.get("bearish_pct")),
        "mentions":       int(data.get("mentions") or 0),
        "trend":          str(data.get("daily_trend") or data.get("trend") or ""),
        "period_days":    int(data.get("period_days") or 7),
        "top_posts":      (data.get("top_posts") or [])[:3],
    }
    _set_cached(cache_key, result)
    return result


def get_adanos_twitter(ticker: str) -> dict:
    """
    X/Twitter (FinTwit) sentiment from adanos.org — buzz score,
    bullish/bearish %, top tweets. No API key required on free tier.
    """
    cache_key = f"adanos_twitter_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _get(f"https://api.adanos.org/twitter/ticker/{ticker.upper()}")

    if not data or "_error" in data or data.get("found") is False:
        result = {
            "source":     "adanos_twitter",
            "ticker":     ticker.upper(),
            "found":      False,
            "buzz_score": None,
            "sentiment":  None,
            "bullish_pct":None,
            "bearish_pct":None,
        }
        _set_cached(cache_key, result)
        return result

    result = {
        "source":          "adanos_twitter",
        "ticker":          ticker.upper(),
        "found":           True,
        "buzz_score":      _sf(data.get("buzz_score")),
        "sentiment_score": _sf(data.get("sentiment_score")),
        "bullish_pct":     _sf(data.get("bullish_pct")),
        "bearish_pct":     _sf(data.get("bearish_pct")),
        "mentions":        int(data.get("mentions") or data.get("unique_tweets") or 0),
        "trend":           str(data.get("trend") or ""),
        "top_tweets":      (data.get("top_tweets") or [])[:3],
        "period_days":     int(data.get("period_days") or 7),
    }
    _set_cached(cache_key, result)
    return result


def get_adanos_trending_reddit() -> list[dict]:
    """Top trending tickers on Reddit right now from adanos."""
    cache_key = "adanos_trending_reddit"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _get("https://api.adanos.org/reddit/trending")
    if not data or "_error" in data:
        return []

    results = []
    for item in (data.get("results") or data if isinstance(data, list) else [])[:20]:
        results.append({
            "ticker":      str(item.get("ticker", "")).upper(),
            "buzz_score":  _sf(item.get("buzz_score")),
            "sentiment":   _sf(item.get("sentiment_score")),
            "bullish_pct": _sf(item.get("bullish_pct")),
            "mentions":    int(item.get("mentions") or 0),
            "trend":       str(item.get("trend") or ""),
        })

    _set_cached(cache_key, results)
    return results


# ─────────────────────────────────────────────────────────────
# Source 3 — StockTwits (public stream, no auth)
# ─────────────────────────────────────────────────────────────

def get_stocktwits(ticker: str) -> dict:
    """
    StockTwits message stream and sentiment for a ticker.
    Public endpoint — no API key required.
    Returns bullish/bearish counts from tagged messages.
    """
    cache_key = f"st_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    data = _get(
        f"https://api.stocktwits.com/api/2/streams/symbol/{ticker.upper()}.json"
    )

    if not data or "_error" in data:
        result = {
            "source":   "stocktwits",
            "ticker":   ticker.upper(),
            "found":    False,
            "bullish":  0,
            "bearish":  0,
            "messages": [],
        }
        _set_cached(cache_key, result)
        return result

    messages    = data.get("messages", [])
    bullish_cnt = 0
    bearish_cnt = 0
    parsed_msgs = []

    for m in messages[:30]:
        sentiment_tag = None
        entities = m.get("entities", {})
        if entities:
            sent_obj = entities.get("sentiment")
            if sent_obj and isinstance(sent_obj, dict):
                sentiment_tag = sent_obj.get("basic", "").lower()

        if sentiment_tag == "bullish":
            bullish_cnt += 1
        elif sentiment_tag == "bearish":
            bearish_cnt += 1

        parsed_msgs.append({
            "user":      m.get("user", {}).get("username", ""),
            "body":      m.get("body", "")[:120],
            "sentiment": sentiment_tag,
            "likes":     m.get("likes", {}).get("total", 0) if isinstance(m.get("likes"), dict) else 0,
            "created":   str(m.get("created_at", ""))[:16],
        })

    total_tagged = bullish_cnt + bearish_cnt
    bull_pct = round(bullish_cnt / total_tagged * 100) if total_tagged > 0 else None

    result = {
        "source":        "stocktwits",
        "ticker":        ticker.upper(),
        "found":         bool(messages),
        "bullish":       bullish_cnt,
        "bearish":       bearish_cnt,
        "total_messages":len(messages),
        "bull_pct":      bull_pct,
        "bear_pct":      100 - bull_pct if bull_pct is not None else None,
        "sentiment_label": (
            "Bullish" if bull_pct and bull_pct > 60 else
            "Bearish" if bull_pct and bull_pct < 40 else
            "Mixed"   if bull_pct is not None else "Untagged"
        ),
        "messages": parsed_msgs[:10],
    }
    _set_cached(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────
# Source 4 — Finnhub news + social sentiment (existing key)
# ─────────────────────────────────────────────────────────────

def get_finnhub_sentiment(ticker: str) -> dict:
    """
    Finnhub news buzz + social sentiment.
    Uses existing FINNHUB_API_KEY.
    """
    cache_key = f"fh_sent_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    key = _get_secret("FINNHUB_API_KEY")
    if not key:
        return {"source": "finnhub", "found": False}

    # News sentiment
    news = _get(
        "https://finnhub.io/api/v1/news-sentiment",
        params={"symbol": ticker.upper(), "token": key},
    )

    result: dict = {
        "source":      "finnhub",
        "ticker":      ticker.upper(),
        "found":       False,
        "buzz_weekly": None,
        "buzz_change": None,
        "news_sentiment_bullish": None,
        "news_sentiment_bearish": None,
        "article_mentions": None,
        "social_bullish": None,
        "social_bearish": None,
    }

    if news and "_error" not in news and news.get("buzz"):
        buzz = news["buzz"]
        sent = news.get("sentiment", {})
        result.update({
            "found":                     True,
            "buzz_weekly":               _sf(buzz.get("weeklyAverage")),
            "buzz_change":               _sf(buzz.get("increment")),
            "article_mentions":          int(buzz.get("articlesInLastWeek") or 0),
            "news_sentiment_bullish":    _sf(sent.get("bullishPercent")),
            "news_sentiment_bearish":    _sf(sent.get("bearishPercent")),
        })

    # Social sentiment (Reddit, Twitter aggregated)
    from datetime import timedelta
    date_from = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    social = _get(
        "https://finnhub.io/api/v1/stock/social-sentiment",
        params={"symbol": ticker.upper(), "from": date_from, "token": key},
    )

    if social and "_error" not in social:
        reddit  = social.get("reddit", [])
        twitter = social.get("twitter", [])
        if reddit:
            latest_r = reddit[-1] if reddit else {}
            result["social_reddit_score"]    = _sf(latest_r.get("score"))
            result["social_reddit_mentions"] = int(latest_r.get("mention") or 0)
            result["found"] = True
        if twitter:
            latest_t = twitter[-1] if twitter else {}
            result["social_twitter_score"]    = _sf(latest_t.get("score"))
            result["social_twitter_mentions"] = int(latest_t.get("mention") or 0)
            result["found"] = True

    _set_cached(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────
# Composite sentiment score
# ─────────────────────────────────────────────────────────────

def get_composite_sentiment(ticker: str) -> dict:
    """
    Aggregate all sources into a single composite sentiment score.
    Score: -100 (very bearish) → 0 (neutral) → +100 (very bullish)

    Weights:
      adanos.org Reddit  40%
      StockTwits         30%
      ApeWisdom buzz     20%
      Finnhub news       10%
    """
    cache_key = f"composite_{ticker}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Fetch all sources (parallel would be ideal but Streamlit is single-threaded)
    reddit  = get_adanos_reddit(ticker)
    twitter = get_adanos_twitter(ticker)
    st_data = get_stocktwits(ticker)
    ape     = get_apewisdom(ticker)
    fh      = get_finnhub_sentiment(ticker)

    scores      = []
    weights     = []
    sources_used= []

    # adanos Reddit (40% weight)
    if reddit.get("found") and reddit.get("sentiment_score") is not None:
        # sentiment_score is -1 to +1 → scale to -100 to +100
        score = float(reddit["sentiment_score"]) * 100
        # Also factor in bull/bear pct
        if reddit.get("bullish_pct") is not None and reddit.get("bearish_pct") is not None:
            pct_score = reddit["bullish_pct"] - reddit["bearish_pct"]
            score = (score + pct_score) / 2
        scores.append(score)
        weights.append(0.40)
        sources_used.append("Reddit (adanos)")
    elif reddit.get("found") and reddit.get("bullish_pct") is not None:
        score = reddit["bullish_pct"] - reddit.get("bearish_pct", 0)
        scores.append(score)
        weights.append(0.40)
        sources_used.append("Reddit (adanos)")

    # adanos Twitter (included in Reddit weight if available)
    if twitter.get("found") and twitter.get("sentiment_score") is not None:
        t_score = float(twitter["sentiment_score"]) * 100
        if twitter.get("bullish_pct") is not None:
            pct_score = twitter["bullish_pct"] - twitter.get("bearish_pct", 0)
            t_score = (t_score + pct_score) / 2
        # Blend into Reddit weight
        if scores:
            scores[-1] = (scores[-1] + t_score) / 2
        else:
            scores.append(t_score)
            weights.append(0.40)
            sources_used.append("X/Twitter (adanos)")

    # StockTwits (30% weight)
    if st_data.get("found") and st_data.get("bull_pct") is not None:
        st_score = st_data["bull_pct"] - st_data.get("bear_pct", 0)
        scores.append(st_score)
        weights.append(0.30)
        sources_used.append("StockTwits")

    # ApeWisdom buzz (20% weight) — use rank change as proxy
    if ape.get("found"):
        rank_chg = ape.get("rank_change") or 0
        # Rising rank = positive buzz, use bounded score
        ape_score = min(50, max(-50, rank_chg * 2))
        # Combine with mention momentum
        if ape.get("mentions_change"):
            m_score = min(50, max(-50, ape["mentions_change"] / 10))
            ape_score = (ape_score + m_score) / 2
        scores.append(ape_score)
        weights.append(0.20)
        sources_used.append("Reddit WSB (ApeWisdom)")

    # Finnhub news (10% weight)
    if fh.get("found"):
        fh_bull = fh.get("news_sentiment_bullish") or 0
        fh_bear = fh.get("news_sentiment_bearish") or 0
        if fh_bull + fh_bear > 0:
            fh_score = fh_bull - fh_bear
            scores.append(fh_score)
            weights.append(0.10)
            sources_used.append("Finnhub News")

    # Compute weighted average
    if scores:
        total_w = sum(weights)
        composite = round(
            sum(s * w for s, w in zip(scores, weights)) / total_w, 1
        )
    else:
        composite = 0.0

    label = (
        "Very Bullish"  if composite > 40 else
        "Bullish"       if composite > 15 else
        "Slightly Bullish" if composite > 5 else
        "Neutral"       if composite > -5 else
        "Slightly Bearish" if composite > -15 else
        "Bearish"       if composite > -40 else
        "Very Bearish"
    )

    result = {
        "ticker":          ticker.upper(),
        "composite_score": composite,
        "label":           label,
        "sources_used":    sources_used,
        "n_sources":       len(sources_used),
        "timestamp":       datetime.now(timezone.utc).isoformat(),
        # Individual source results
        "reddit":          reddit,
        "twitter":         twitter,
        "stocktwits":      st_data,
        "apewisdom":       ape,
        "finnhub":         fh,
    }

    _set_cached(cache_key, result)
    return result


# ─────────────────────────────────────────────────────────────
# Market-wide trending (no ticker needed)
# ─────────────────────────────────────────────────────────────

def get_trending_tickers() -> dict:
    """
    Get currently trending tickers across Reddit and X/Twitter.
    No ticker needed — market-wide signal.
    """
    cache_key = "trending_all"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    ape_trending = get_apewisdom_trending(25)
    adanos_trending = get_adanos_trending_reddit()

    result = {
        "reddit_wsb":  ape_trending,
        "reddit_all":  adanos_trending,
        "timestamp":   datetime.now(timezone.utc).isoformat(),
    }
    _set_cached(cache_key, result)
    return result