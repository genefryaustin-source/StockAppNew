"""
modules/analytics/news_provider.py

Institutional news ingestion layer.

Responsibilities:
- Finnhub ingestion
- normalization
- caching
- deduplication
- provider abstraction

Future:
- Reuters
- Polygon
- Benzinga
- SEC filings
- earnings transcripts
- embeddings/vector storage
"""

from __future__ import annotations

import time
import hashlib
from datetime import datetime, UTC, timedelta
from typing import Dict, List, Optional, Any

import requests
import streamlit as st


# ---------------------------------------------------
# CACHE
# ---------------------------------------------------

_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}

CACHE_TTL_SECONDS = 900  # 15 minutes


# ---------------------------------------------------
# FINNHUB
# ---------------------------------------------------

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------

def _cache_key(
    symbol: str,
    days_back: int,
) -> str:

    return f"{symbol.upper()}::{days_back}"


def _now_ts() -> float:
    return time.time()


def _is_cache_valid(
    cache_entry: Optional[Dict[str, Any]],
) -> bool:

    if not cache_entry:
        return False

    ts = cache_entry.get("timestamp")

    if ts is None:
        return False

    return (_now_ts() - ts) < CACHE_TTL_SECONDS


def _safe_get_secret(
    key_name: str,
) -> Optional[str]:

    try:
        return st.secrets.get(key_name)

    except Exception:
        return None


def _safe_json(
    response: requests.Response,
) -> Any:

    try:
        return response.json()

    except Exception:
        return None


# ---------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------

def normalize_news_item(
    symbol: str,
    item: Dict[str, Any],
    provider: str = "finnhub",
) -> Dict[str, Any]:

    headline = (
        item.get("headline")
        or item.get("title")
        or ""
    )

    summary = (
        item.get("summary")
        or item.get("description")
        or ""
    )

    source = (
        item.get("source")
        or provider
    )

    url = (
        item.get("url")
        or ""
    )

    published_raw = (
        item.get("datetime")
        or item.get("published_at")
        or item.get("time")
    )

    published_at = None

    try:

        # Finnhub epoch timestamp
        if isinstance(published_raw, (int, float)):

            published_at = datetime.fromtimestamp(
                published_raw,
                tz=UTC,
            )

        elif isinstance(published_raw, str):

            try:

                published_at = datetime.fromisoformat(
                    published_raw
                )

            except Exception:

                published_at = None

    except Exception:

        published_at = None

    normalized = {

        "symbol": symbol.upper(),

        "headline": str(headline).strip(),

        "summary": str(summary).strip(),

        "source": str(source).strip(),

        "url": str(url).strip(),

        "published_at": published_at,

        "provider": provider,
    }

    return normalized


# ---------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------

def _dedupe_key(
    article: Dict[str, Any],
) -> str:

    raw = (
        f"{article.get('headline','')}|"
        f"{article.get('source','')}|"
        f"{article.get('url','')}"
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def dedupe_news(
    articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    seen = set()

    output = []

    for article in articles:

        try:

            key = _dedupe_key(article)

            if key in seen:
                continue

            seen.add(key)

            output.append(article)

        except Exception:
            continue

    return output


# ---------------------------------------------------
# FINNHUB INGESTION
# ---------------------------------------------------

def fetch_finnhub_company_news(
    symbol: str,
    days_back: int = 7,
) -> List[Dict[str, Any]]:

    api_key = _safe_get_secret(
        "FINNHUB_API_KEY"
    )

    if not api_key:

        print(
            "FINNHUB NEWS: API KEY MISSING"
        )

        return []

    now = datetime.now(UTC)

    start = (
        now - timedelta(days=days_back)
    ).strftime("%Y-%m-%d")

    end = now.strftime("%Y-%m-%d")

    try:

        r = requests.get(

            f"{FINNHUB_BASE_URL}/company-news",

            params={

                "symbol": symbol.upper(),

                "from": start,

                "to": end,

                "token": api_key,
            },

            timeout=20,
        )

        if r.status_code != 200:

            print(
                "FINNHUB NEWS STATUS ERROR",
                r.status_code,
                r.text[:200],
            )

            return []

        data = _safe_json(r)

        if not isinstance(data, list):
            return []

        normalized = []

        for item in data:

            try:

                normalized.append(
                    normalize_news_item(
                        symbol=symbol,
                        item=item,
                        provider="finnhub",
                    )
                )

            except Exception as e:

                print(
                    "NEWS NORMALIZATION ERROR",
                    symbol,
                    e,
                )

        return dedupe_news(normalized)

    except Exception as e:

        print(
            "FINNHUB NEWS FETCH ERROR",
            symbol,
            e,
        )

        return []


# ---------------------------------------------------
# PROVIDER ROUTER
# ---------------------------------------------------

def fetch_news_from_all_providers(
    symbol: str,
    days_back: int = 7,
) -> List[Dict[str, Any]]:

    articles = []

    # -----------------------------------
    # Finnhub
    # -----------------------------------

    try:

        articles.extend(

            fetch_finnhub_company_news(
                symbol=symbol,
                days_back=days_back,
            )
        )

    except Exception as e:

        print(
            "FINNHUB PROVIDER ERROR",
            symbol,
            e,
        )

    # -----------------------------------
    # FUTURE PROVIDERS
    # -----------------------------------
    #
    # Reuters
    # Polygon
    # Benzinga
    # SEC filings
    # etc.
    #
    # -----------------------------------

    articles = dedupe_news(articles)

    return articles


# ---------------------------------------------------
# MAIN ENTRY
# ---------------------------------------------------

def get_symbol_news(
    symbol: str,
    days_back: int = 7,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:

    symbol = str(symbol).upper().strip()

    if not symbol:
        return []

    key = _cache_key(
        symbol,
        days_back,
    )

    # -----------------------------------
    # CACHE HIT
    # -----------------------------------

    if not force_refresh:

        cached = _NEWS_CACHE.get(key)

        if _is_cache_valid(cached):

            return cached.get(
                "articles",
                [],
            )

    # -----------------------------------
    # FETCH
    # -----------------------------------

    articles = fetch_news_from_all_providers(
        symbol=symbol,
        days_back=days_back,
    )

    # -----------------------------------
    # STORE CACHE
    # -----------------------------------

    _NEWS_CACHE[key] = {

        "timestamp": _now_ts(),

        "articles": articles,
    }

    return articles


# ---------------------------------------------------
# BATCH NEWS
# ---------------------------------------------------

def get_news_batch(
    symbols: List[str],
    days_back: int = 7,
    max_symbols: Optional[int] = None,
) -> Dict[str, List[Dict[str, Any]]]:

    output = {}

    clean_symbols = [

        str(s).upper().strip()

        for s in symbols

        if s and str(s).strip()
    ]

    if max_symbols is not None:

        clean_symbols = clean_symbols[:max_symbols]

    for symbol in clean_symbols:

        try:

            output[symbol] = get_symbol_news(
                symbol=symbol,
                days_back=days_back,
            )

        except Exception as e:

            print(
                "BATCH NEWS ERROR",
                symbol,
                e,
            )

            output[symbol] = []

    return output


# ---------------------------------------------------
# CACHE MANAGEMENT
# ---------------------------------------------------

def clear_news_cache():

    global _NEWS_CACHE

    _NEWS_CACHE = {}


def get_news_cache_stats() -> Dict[str, Any]:

    return {

        "entries": len(_NEWS_CACHE),

        "ttl_seconds": CACHE_TTL_SECONDS,
    }