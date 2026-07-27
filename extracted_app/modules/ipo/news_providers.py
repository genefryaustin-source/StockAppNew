# ============================================================
# modules/ipo/news_providers.py
# IPO & Pre-IPO News Providers
# Fetches from: NewsAPI, Finnhub company news, RSS feeds
# (Renaissance Capital, IPO Monitor, SEC EDGAR full-text search)
# ============================================================

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import requests

from modules.utils.config import get_secret


DEFAULT_TIMEOUT = 15

# ---------------------------------------------------------------------------
# Free / no-key RSS sources covering IPO news
# ---------------------------------------------------------------------------
IPO_RSS_FEEDS = [
    {
        "name": "Renaissance Capital",
        "url": "https://www.renaissancecapital.com/review/IPOScoop.xml",
        "source_label": "Renaissance Capital",
    },
    {
        "name": "IPO Monitor",
        "url": "https://www.ipomonitor.com/rss/ipomonitor.rss",
        "source_label": "IPO Monitor",
    },
    {
        "name": "Seeking Alpha IPO",
        "url": "https://seekingalpha.com/tag/ipo.xml",
        "source_label": "Seeking Alpha",
    },
    {
        "name": "Yahoo Finance IPO",
        "url": "https://feeds.finance.yahoo.com/rss/2.0/headline?s=ipo&region=US&lang=en-US",
        "source_label": "Yahoo Finance",
    },
    {
        "name": "MarketWatch IPO",
        "url": "https://feeds.marketwatch.com/marketwatch/marketpulse/",
        "source_label": "MarketWatch",
    },
]

# Tickr-style pre-IPO keyword targets
PRE_IPO_KEYWORDS = [
    "IPO", "S-1", "pre-IPO", "pre IPO", "going public", "initial public offering",
    "SPAC", "direct listing", "roadshow", "unicorn IPO", "venture IPO",
    "IPO filing", "IPO calendar", "IPO pipeline", "IPO pricing",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(url: str, params: Dict = None, headers: Dict = None, timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
    try:
        resp = requests.get(url, params=params or {}, headers=headers or {}, timeout=timeout)
        if resp.status_code == 200:
            return resp
        return None
    except Exception as e:
        print(f"[news_providers] HTTP error {url}: {e}")
        return None


def _parse_rss_date(value: Any) -> Optional[datetime]:
    if not value:
        return None
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]:
        try:
            dt = datetime.strptime(str(value).strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt
        except ValueError:
            continue
    return None


def _clean_html(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", " ", text).strip()


def _sentiment_heuristic(text: str) -> str:
    """
    Very lightweight rule-based sentiment tagger.
    Returns: 'Bullish' | 'Bearish' | 'Neutral'
    Replaced by LLM enrichment in the service layer when available.
    """
    text_lower = (text or "").lower()

    bullish_signals = [
        "surged", "soared", "jumped", "climbed", "rallied", "strong demand",
        "oversubscribed", "raised guidance", "beat", "revenue growth", "record",
        "profitable", "unicorn", "successful ipo", "priced above", "above range",
    ]
    bearish_signals = [
        "withdrew", "postponed", "delayed", "cut price", "below range", "fell",
        "missed", "loss", "declining", "pulled", "canceled", "weak demand",
        "volatile", "concerns", "risky", "downgraded", "regulatory risk",
    ]

    bull_count = sum(1 for w in bullish_signals if w in text_lower)
    bear_count = sum(1 for w in bearish_signals if w in text_lower)

    if bull_count > bear_count:
        return "Bullish"
    if bear_count > bull_count:
        return "Bearish"
    return "Neutral"


def _is_ipo_relevant(text: str) -> bool:
    text_upper = text.upper()
    return any(kw.upper() in text_upper for kw in PRE_IPO_KEYWORDS)


def _normalize_article(
    title: str,
    url: str,
    published_at: Optional[datetime],
    summary: str,
    source_label: str,
    company_hint: Optional[str] = None,
) -> Dict[str, Any]:
    full_text = f"{title} {summary}"
    return {
        "title": (title or "").strip(),
        "url": (url or "").strip(),
        "published_at": published_at,
        "summary": _clean_html(summary or "")[:800],
        "source": source_label,
        "sentiment": _sentiment_heuristic(full_text),
        "company_hint": company_hint,
        "ipo_relevant": _is_ipo_relevant(full_text),
    }


# ---------------------------------------------------------------------------
# RSS Feed Fetcher
# ---------------------------------------------------------------------------

def fetch_rss_ipo_news(max_per_feed: int = 20) -> List[Dict[str, Any]]:
    articles = []

    for feed in IPO_RSS_FEEDS:
        resp = _safe_get(feed["url"])
        if not resp:
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            continue

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        count = 0

        for item in items:
            if count >= max_per_feed:
                break

            def _txt(tag):
                el = item.find(tag)
                if el is None:
                    for ns_uri in ["http://www.w3.org/2005/Atom"]:
                        el = item.find(f"{{{ns_uri}}}{tag}")
                return (el.text or "").strip() if el is not None and el.text else ""

            title = _txt("title")
            link = _txt("link") or _txt("guid")
            pub_date = _parse_rss_date(_txt("pubDate") or _txt("published") or _txt("updated"))
            description = _txt("description") or _txt("summary") or _txt("content")

            if not title:
                continue

            full_text = f"{title} {description}"
            if not _is_ipo_relevant(full_text):
                continue

            articles.append(_normalize_article(
                title=title,
                url=link,
                published_at=pub_date,
                summary=description,
                source_label=feed["source_label"],
            ))
            count += 1

    return articles


# ---------------------------------------------------------------------------
# Finnhub Company News
# ---------------------------------------------------------------------------

def fetch_finnhub_company_news(
    symbol: str,
    days_back: int = 14,
) -> List[Dict[str, Any]]:
    key = get_secret("FINNHUB_API_KEY")
    if not key or not symbol:
        return []

    end = datetime.now(UTC)
    start = end - timedelta(days=days_back)

    resp = _safe_get(
        "https://finnhub.io/api/v1/company-news",
        params={
            "symbol": symbol.upper(),
            "from": start.strftime("%Y-%m-%d"),
            "to": end.strftime("%Y-%m-%d"),
            "token": key,
        },
    )

    if not resp:
        return []

    articles = []
    for item in resp.json() or []:
        if not isinstance(item, dict):
            continue
        pub = None
        ts = item.get("datetime")
        if ts:
            try:
                pub = datetime.fromtimestamp(int(ts), tz=UTC)
            except Exception:
                pass

        articles.append(_normalize_article(
            title=item.get("headline", ""),
            url=item.get("url", ""),
            published_at=pub,
            summary=item.get("summary", ""),
            source_label=item.get("source", "Finnhub"),
            company_hint=symbol.upper(),
        ))

    return articles


# ---------------------------------------------------------------------------
# NewsAPI  (requires NEWSAPI_KEY secret)
# ---------------------------------------------------------------------------

def fetch_newsapi_ipo_news(
    query: str = "IPO OR \"going public\" OR \"S-1 filing\" OR pre-IPO",
    days_back: int = 7,
    page_size: int = 30,
) -> List[Dict[str, Any]]:
    key = get_secret("NEWSAPI_KEY") or get_secret("NEWS_API_KEY")
    if not key:
        return []

    from_dt = (datetime.now(UTC) - timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%M:%SZ")

    resp = _safe_get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "from": from_dt,
            "sortBy": "publishedAt",
            "pageSize": page_size,
            "language": "en",
            "apiKey": key,
        },
    )

    if not resp:
        return []

    articles = []
    for item in (resp.json() or {}).get("articles", []):
        if not isinstance(item, dict):
            continue
        pub = None
        try:
            pub = datetime.fromisoformat(item.get("publishedAt", "").replace("Z", "+00:00"))
        except Exception:
            pass

        articles.append(_normalize_article(
            title=item.get("title", ""),
            url=item.get("url", ""),
            published_at=pub,
            summary=item.get("description", "") or item.get("content", ""),
            source_label=(item.get("source") or {}).get("name", "NewsAPI"),
        ))

    return articles


# ---------------------------------------------------------------------------
# Finnhub General IPO-related market news
# ---------------------------------------------------------------------------

def fetch_finnhub_market_news(
    category: str = "ipo",
    min_id: int = 0,
) -> List[Dict[str, Any]]:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []

    resp = _safe_get(
        "https://finnhub.io/api/v1/news",
        params={"category": category, "minId": min_id, "token": key},
    )

    if not resp:
        return []

    articles = []
    for item in resp.json() or []:
        if not isinstance(item, dict):
            continue
        pub = None
        ts = item.get("datetime")
        if ts:
            try:
                pub = datetime.fromtimestamp(int(ts), tz=UTC)
            except Exception:
                pass

        articles.append(_normalize_article(
            title=item.get("headline", ""),
            url=item.get("url", ""),
            published_at=pub,
            summary=item.get("summary", ""),
            source_label=item.get("source", "Finnhub Market News"),
        ))

    return articles


# ---------------------------------------------------------------------------
# Aggregate entrypoint
# ---------------------------------------------------------------------------

def fetch_all_ipo_news(
    days_back: int = 7,
    symbol: Optional[str] = None,
    include_rss: bool = True,
    include_newsapi: bool = True,
    include_finnhub_market: bool = True,
) -> List[Dict[str, Any]]:
    """
    Aggregate all IPO/pre-IPO news from all configured providers.
    Deduplicates by URL.
    """
    results: List[Dict[str, Any]] = []
    seen_urls: set = set()

    if include_rss:
        results.extend(fetch_rss_ipo_news())

    if include_finnhub_market:
        results.extend(fetch_finnhub_market_news())

    if include_newsapi:
        results.extend(fetch_newsapi_ipo_news(days_back=days_back))

    if symbol:
        results.extend(fetch_finnhub_company_news(symbol=symbol, days_back=days_back))

    deduped = []
    for item in results:
        url = item.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(item)
        elif not url:
            deduped.append(item)

    # Sort newest first
    deduped.sort(
        key=lambda x: x.get("published_at") or datetime.min.replace(tzinfo=UTC),
        reverse=True,
    )

    return deduped