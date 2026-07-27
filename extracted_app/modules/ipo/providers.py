# ============================================================
# modules/ipo/providers.py
# IPO provider clients: Finnhub primary, FMP fallback
# ============================================================

from __future__ import annotations

import json
from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

import requests

from modules.utils.config import get_secret


FINNHUB_IPO_URL = "https://finnhub.io/api/v1/calendar/ipo"
FMP_IPO_URLS = [
    "https://financialmodelingprep.com/api/v3/ipo_calendar",
    "https://financialmodelingprep.com/stable/ipos-calendar",
]
DEFAULT_TIMEOUT = 15


def _parse_date(value: Any):
    if not value:
        return None

    try:
        text = str(value).strip()
        if not text:
            return None

        if len(text) == 10:
            return datetime.fromisoformat(text).replace(tzinfo=UTC)

        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(UTC)
    except Exception:
        return None


def _to_float(value: Any):
    try:
        if value in (None, "", "None", "null", "N/A"):
            return None
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").strip()
        return float(value)
    except Exception:
        return None


def _split_price_range(value: Any):
    if value in (None, "", "N/A"):
        return None, None

    text = str(value).replace("$", "").replace(",", "").strip()

    for sep in ["-", "to", "–", "—"]:
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2:
                return _to_float(parts[0]), _to_float(parts[1])

    val = _to_float(text)
    return val, val


def _normalize_finnhub_item(item: Dict[str, Any]) -> Dict[str, Any]:
    company = (
        item.get("name")
        or item.get("company")
        or item.get("companyName")
        or item.get("issuer")
        or "Unknown"
    )

    symbol = item.get("symbol") or item.get("ticker")
    exchange = item.get("exchange")
    ipo_date = _parse_date(item.get("date") or item.get("ipoDate") or item.get("pricedDate"))

    price_low = _to_float(item.get("priceFrom") or item.get("priceLow"))
    price_high = _to_float(item.get("priceTo") or item.get("priceHigh"))

    if price_low is None and price_high is None:
        price_low, price_high = _split_price_range(item.get("price"))

    price = _to_float(item.get("price"))
    if price is None and price_low is not None and price_high is not None:
        price = (price_low + price_high) / 2.0

    shares = _to_float(item.get("numberOfShares") or item.get("shares"))
    deal_size = _to_float(item.get("totalSharesValue") or item.get("dealSize"))

    return {
        "symbol": str(symbol).upper().strip() if symbol else None,
        "company_name": str(company).strip(),
        "exchange": exchange,
        "ipo_date": ipo_date,
        "status": item.get("status") or "upcoming",
        "price": price,
        "price_low": price_low,
        "price_high": price_high,
        "shares": shares,
        "deal_size": deal_size,
        "market_cap": _to_float(item.get("marketCap")),
        "sector": item.get("sector"),
        "industry": item.get("industry"),
        "country": item.get("country"),
        "underwriters": item.get("underwriters"),
        "description": item.get("description"),
        "source": "FINNHUB",
        "raw_payload": json.dumps(item, default=str),
    }


def _normalize_fmp_item(item: Dict[str, Any]) -> Dict[str, Any]:
    company = (
        item.get("company")
        or item.get("companyName")
        or item.get("name")
        or "Unknown"
    )

    symbol = item.get("symbol") or item.get("ticker")
    ipo_date = _parse_date(item.get("date") or item.get("ipoDate"))

    price_low = _to_float(item.get("priceLow"))
    price_high = _to_float(item.get("priceHigh"))

    if price_low is None and price_high is None:
        price_low, price_high = _split_price_range(item.get("priceRange"))

    price = _to_float(item.get("price"))
    if price is None and price_low is not None and price_high is not None:
        price = (price_low + price_high) / 2.0

    shares = _to_float(item.get("shares") or item.get("numberOfShares"))
    deal_size = _to_float(item.get("dealSize") or item.get("marketCap"))

    return {
        "symbol": str(symbol).upper().strip() if symbol else None,
        "company_name": str(company).strip(),
        "exchange": item.get("exchange"),
        "ipo_date": ipo_date,
        "status": item.get("status") or "upcoming",
        "price": price,
        "price_low": price_low,
        "price_high": price_high,
        "shares": shares,
        "deal_size": deal_size,
        "market_cap": _to_float(item.get("marketCap")),
        "sector": item.get("sector"),
        "industry": item.get("industry"),
        "country": item.get("country"),
        "underwriters": item.get("underwriters"),
        "description": item.get("description"),
        "source": "FMP",
        "raw_payload": json.dumps(item, default=str),
    }


def fetch_finnhub_ipo_calendar(
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    key = get_secret("FINNHUB_API_KEY")
    if not key:
        return []

    response = requests.get(
        FINNHUB_IPO_URL,
        params={
            "from": start_date,
            "to": end_date,
            "token": key,
        },
        timeout=DEFAULT_TIMEOUT,
    )

    if response.status_code != 200:
        print("FINNHUB IPO ERROR:", response.status_code, response.text[:300])
        return []

    data = response.json()
    items = data.get("ipoCalendar") or data.get("data") or data.get("results") or []

    return [_normalize_finnhub_item(item) for item in items if isinstance(item, dict)]


def fetch_fmp_ipo_calendar(
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    key = get_secret("FMP_API_KEY")
    if not key:
        return []

    for url in FMP_IPO_URLS:
        try:
            response = requests.get(
                url,
                params={
                    "from": start_date,
                    "to": end_date,
                    "apikey": key,
                },
                timeout=DEFAULT_TIMEOUT,
            )

            if response.status_code != 200:
                continue

            data = response.json()
            if isinstance(data, dict):
                items = data.get("data") or data.get("results") or []
            elif isinstance(data, list):
                items = data
            else:
                items = []

            if items:
                return [_normalize_fmp_item(item) for item in items if isinstance(item, dict)]

        except Exception as e:
            print("FMP IPO ERROR:", e)

    return []


def fetch_ipo_calendar(
    start_date: str,
    end_date: str,
) -> List[Dict[str, Any]]:
    """
    Fetch IPO calendar with provider fallback.
    Primary: Finnhub.
    Secondary: FMP.
    """
    rows = fetch_finnhub_ipo_calendar(start_date, end_date)

    if rows:
        return rows

    return fetch_fmp_ipo_calendar(start_date, end_date)
