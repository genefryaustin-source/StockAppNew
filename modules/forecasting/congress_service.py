"""
modules/forecasting/congress_service.py

Fetches Congressional trading disclosures for a given ticker.

Primary source  : Quiver Quant API  (set QUIVER_API_KEY in env/secrets)
Secondary source: House Stock Watcher JSON (free, no key needed)
Fallback        : Returns empty list with an explanation

Usage:
    from modules.forecasting.congress_service import get_congress_trades
    trades = get_congress_trades("NVDA")
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests

# Simple in-process cache to avoid hammering APIs
_CACHE: dict = {}
_CACHE_TTL = 3600  # 1 hour


def get_congress_trades(
    symbol: str,
    days_back: int = 180,
) -> list[dict]:
    """
    Returns a list of congressional trade disclosures for `symbol`.

    Each item is a dict with keys:
        member       : str
        party        : str  ("D" | "R" | "I" | "")
        chamber      : str  ("House" | "Senate" | "")
        trade_type   : str  ("buy" | "sell" | "exchange")
        amount_range : str  (e.g. "$1,001–$15,000")
        trade_date   : str  (ISO date or "Unknown")
        disclosure_date : str
        delay_days   : int | None
        ticker       : str
        asset_description : str
    """
    key = f"{symbol.upper()}_{days_back}"
    cached = _CACHE.get(key)
    if cached and (time.time() - cached["ts"]) < _CACHE_TTL:
        return cached["data"]

    result = (
        _fetch_quiver(symbol, days_back)
        or _fetch_house_stock_watcher(symbol, days_back)
        or []
    )

    _CACHE[key] = {"ts": time.time(), "data": result}
    return result


# ─────────────────────────────────────────────────────────────
# Source 1: Quiver Quant
# ─────────────────────────────────────────────────────────────

def _fetch_quiver(symbol: str, days_back: int) -> Optional[list[dict]]:
    from modules.admin.tenant_api_keys import get_provider_key
    api_key = get_provider_key("QUIVER_API_KEY") or get_provider_key("QUIVERQUANT_API_KEY")
    if not api_key:
        return None

    try:
        url = f"https://api.quiverquant.com/beta/historical/congresstrading/{symbol}"
        resp = requests.get(
            url,
            headers={"Authorization": f"Token {api_key}"},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        cutoff = _days_ago_iso(days_back)
        results = []

        for item in data:
            trade_date = item.get("Date", "") or item.get("TransactionDate", "")
            if trade_date < cutoff:
                continue

            disclosure_date = item.get("ReportDate", "") or item.get("DisclosureDate", "")
            delay = _calc_delay(trade_date, disclosure_date)

            transaction = (item.get("Transaction") or item.get("TransactionType") or "").lower()
            if "purchase" in transaction or "buy" in transaction:
                trade_type = "buy"
            elif "sale" in transaction or "sell" in transaction:
                trade_type = "sell"
            else:
                trade_type = "exchange"

            results.append({
                "member":       item.get("Representative") or item.get("Name") or "Unknown",
                "party":        item.get("Party") or "",
                "chamber":      item.get("Chamber") or "House",
                "trade_type":   trade_type,
                "amount_range": item.get("Amount") or item.get("Range") or "Undisclosed",
                "trade_date":   trade_date,
                "disclosure_date": disclosure_date,
                "delay_days":   delay,
                "ticker":       symbol.upper(),
                "asset_description": item.get("Asset") or symbol.upper(),
            })

        return sorted(results, key=lambda x: x["trade_date"], reverse=True)

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Source 2: House Stock Watcher (free, no key)
# ─────────────────────────────────────────────────────────────

def _fetch_house_stock_watcher(symbol: str, days_back: int) -> Optional[list[dict]]:
    try:
        url = "https://house-stock-watcher-data.s3-us-gov-west-1.amazonaws.com/data/all_transactions.json"
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        cutoff = _days_ago_iso(days_back)
        sym_upper = symbol.upper()
        results = []

        for item in data:
            if (item.get("ticker") or "").upper() != sym_upper:
                continue

            trade_date = item.get("transaction_date", "") or ""
            if trade_date < cutoff:
                continue

            disclosure_date = item.get("disclosure_date", "") or ""
            delay = _calc_delay(trade_date, disclosure_date)

            tx = (item.get("type") or "").lower()
            if "purchase" in tx or "buy" in tx:
                trade_type = "buy"
            elif "sale" in tx or "sell" in tx:
                trade_type = "sell"
            else:
                trade_type = "exchange"

            results.append({
                "member":       item.get("representative") or "Unknown",
                "party":        item.get("party") or "",
                "chamber":      "House",
                "trade_type":   trade_type,
                "amount_range": item.get("amount") or "Undisclosed",
                "trade_date":   trade_date,
                "disclosure_date": disclosure_date,
                "delay_days":   delay,
                "ticker":       sym_upper,
                "asset_description": item.get("asset_description") or sym_upper,
            })

        return sorted(results, key=lambda x: x["trade_date"], reverse=True)

    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _days_ago_iso(days: int) -> str:
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return cutoff.strftime("%Y-%m-%d")


def _calc_delay(trade_date: str, disclosure_date: str) -> Optional[int]:
    try:
        t = datetime.fromisoformat(trade_date[:10])
        d = datetime.fromisoformat(disclosure_date[:10])
        return max(0, (d - t).days)
    except Exception:
        return None