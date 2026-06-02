"""
modules/options_flow/flow_service.py

Unusual Whales API client — Options Flow, Dark Pool, GEX, Insider Flow.

Verified endpoints from https://api.unusualwhales.com/docs:
  GET /api/option-trades/flow-alerts        — unusual flow alerts
  GET /api/darkpool/recent                  — recent dark pool prints
  GET /api/darkpool/{ticker}                — ticker dark pool
  GET /api/stock/{ticker}/options-volume    — volume + P/C ratio
  GET /api/stock/{ticker}/greek-exposure    — GEX
  GET /api/market/market-tide               — market sentiment
  GET /api/insider/{ticker}/ticker-flow     — insider transactions

Requires UNUSUAL_WHALES_API_KEY in Streamlit secrets or environment.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import requests
import streamlit as st

_BASE_URL  = "https://api.unusualwhales.com"
_CACHE_TTL = 60   # seconds
_TIMEOUT   = 10
_CACHE: dict = {}


# ─────────────────────────────────────────────────────────────
# Auth & request
# ─────────────────────────────────────────────────────────────

def _get_key() -> Optional[str]:
    try:
        return (
            os.getenv("UNUSUAL_WHALES_API_KEY")
            or st.secrets.get("UNUSUAL_WHALES_API_KEY", "")
        ) or None
    except Exception:
        return None


def api_available() -> bool:
    return bool(_get_key())


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_key()}",
        "Accept":        "application/json",
    }


def _get(endpoint: str, params: dict = None, ttl: int = _CACHE_TTL) -> Optional[dict]:
    import time
    cache_key = f"{endpoint}_{params}"
    cached = _CACHE.get(cache_key)
    if cached and time.time() - cached["ts"] < ttl:
        return cached["data"]

    try:
        r = requests.get(
            f"{_BASE_URL}{endpoint}",
            headers=_headers(),
            params=params or {},
            timeout=_TIMEOUT,
        )
        if r.status_code == 401:
            return {"_error": "Invalid or missing UNUSUAL_WHALES_API_KEY"}
        if r.status_code == 403:
            return {"_error": "API key does not have access to this endpoint"}
        if r.status_code == 429:
            return {"_error": "Rate limit — try again shortly"}
        r.raise_for_status()
        data = r.json()
        _CACHE[cache_key] = {"data": data, "ts": time.time()}
        return data
    except Exception as e:
        return {"_error": str(e)}


def _safe_float(v) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except Exception:
        return None


def _fmt_ts(ts) -> str:
    if not ts:
        return ""
    try:
        return str(ts)[:19].replace("T", " ")
    except Exception:
        return str(ts)


def _side_label(s: str) -> str:
    s = str(s).lower()
    if "ask" in s or "above" in s:
        return "Ask 🐂"
    if "bid" in s or "below" in s:
        return "Bid 🐻"
    return s.title()


# ─────────────────────────────────────────────────────────────
# Options Flow Alerts  (correct endpoint: /api/option-trades/flow-alerts)
# ─────────────────────────────────────────────────────────────

def get_options_flow(
    ticker: Optional[str] = None,
    min_premium: int = 50_000,
    limit: int = 50,
) -> list[dict]:
    """
    Unusual options flow via /api/option-trades/flow-alerts.
    Pass ticker to filter by symbol, otherwise returns market-wide flow.
    """
    params: dict = {"limit": limit}
    if ticker:
        params["ticker"] = ticker.upper()

    data = _get("/api/option-trades/flow-alerts", params)

    if not data or isinstance(data, dict) and "_error" in data:
        err = data.get("_error", "Unknown error") if data else "No data"
        return [{"_error": err}]

    raw = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []

    results = []
    for item in raw:
        premium = _safe_float(
            item.get("premium") or item.get("total_premium") or 0
        ) or 0
        if premium < min_premium:
            continue

        opt_type = str(item.get("type") or item.get("option_type") or item.get("call_put") or "").upper()
        results.append({
            "ticker":           str(item.get("ticker") or item.get("symbol") or "").upper(),
            "expiry":           str(item.get("expiry") or item.get("expiration_date") or "")[:10],
            "strike":           _safe_float(item.get("strike")),
            "type":             opt_type,
            "premium":          round(premium),
            "premium_fmt":      f"${premium/1e6:.2f}M" if premium >= 1e6 else f"${premium/1e3:.0f}K",
            "size":             int(item.get("size") or item.get("volume") or 0),
            "open_interest":    int(item.get("open_interest") or item.get("oi") or 0),
            "sentiment":        "BULLISH" if opt_type == "CALL" else "BEARISH" if opt_type == "PUT" else "NEUTRAL",
            "is_sweep":         bool(item.get("is_sweep") or item.get("sweep")),
            "is_block":         bool(item.get("is_block") or item.get("block")),
            "side":             _side_label(str(item.get("ask_side") or item.get("side") or "")),
            "underlying_price": _safe_float(item.get("underlying_price") or item.get("price") or item.get("stock_price")),
            "iv":               _safe_float(item.get("iv") or item.get("implied_volatility")),
            "unusual_score":    _safe_float(item.get("unusual_score") or item.get("score")),
            "timestamp":        _fmt_ts(item.get("created_at") or item.get("date")),
        })

    return sorted(results, key=lambda x: x["premium"], reverse=True)


# ─────────────────────────────────────────────────────────────
# Dark Pool  (/api/darkpool/recent  and  /api/darkpool/{ticker})
# ─────────────────────────────────────────────────────────────

def get_darkpool_flow(
    ticker: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Recent dark pool prints."""
    if ticker:
        data = _get(f"/api/darkpool/{ticker.upper()}", {"limit": limit})
    else:
        data = _get("/api/darkpool/recent", {"limit": limit})

    if not data or isinstance(data, dict) and "_error" in data:
        err = data.get("_error", "No data") if data else "No data"
        return [{"_error": err}]

    raw = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []

    results = []
    for item in raw:
        size     = int(item.get("size") or item.get("volume") or item.get("quantity") or 0)
        price    = _safe_float(item.get("price") or item.get("executed_price")) or 0
        notional = size * price if size and price else _safe_float(item.get("notional") or item.get("premium")) or 0
        results.append({
            "ticker":        str(item.get("ticker") or item.get("symbol") or "").upper(),
            "time":          _fmt_ts(item.get("executed_at") or item.get("date") or item.get("timestamp")),
            "price":         price,
            "size":          size,
            "notional":      notional,
            "notional_fmt":  f"${notional/1e6:.2f}M" if notional >= 1e6 else f"${notional/1e3:.0f}K",
            "exchange":      str(item.get("exchange") or item.get("venue") or "ATS"),
        })

    return sorted(results, key=lambda x: x["notional"], reverse=True)


# ─────────────────────────────────────────────────────────────
# Options Volume / P-C Ratio
# ─────────────────────────────────────────────────────────────

def get_options_sentiment(ticker: str) -> dict:
    """P/C ratio and options volume for a ticker."""
    data = _get(f"/api/stock/{ticker.upper()}/options-volume")

    if not data or isinstance(data, dict) and "_error" in data:
        return {"_error": data.get("_error", "No data") if data else "No data"}

    d = data.get("data", data) if isinstance(data, dict) else {}
    if isinstance(d, list) and d:
        d = d[0]
    if not isinstance(d, dict):
        d = {}

    call_vol = _safe_float(d.get("call_volume") or d.get("calls_volume")) or 0
    put_vol  = _safe_float(d.get("put_volume")  or d.get("puts_volume"))  or 0
    pc_ratio = round(put_vol / call_vol, 3) if call_vol > 0 else 0

    return {
        "ticker":       ticker.upper(),
        "call_volume":  int(call_vol),
        "put_volume":   int(put_vol),
        "total_volume": int(call_vol + put_vol),
        "pc_ratio":     pc_ratio,
        "pc_label":     "Bullish" if pc_ratio < 0.7 else "Bearish" if pc_ratio > 1.3 else "Neutral",
        "call_premium": _safe_float(d.get("call_premium")) or 0,
        "put_premium":  _safe_float(d.get("put_premium"))  or 0,
    }


# ─────────────────────────────────────────────────────────────
# GEX
# ─────────────────────────────────────────────────────────────

def get_greek_exposure(ticker: str) -> dict:
    """Gamma exposure for a ticker."""
    data = _get(f"/api/stock/{ticker.upper()}/greek-exposure")

    if not data or isinstance(data, dict) and "_error" in data:
        return {"_error": data.get("_error", "No data") if data else "No data"}

    d = data.get("data", data) if isinstance(data, dict) else {}
    if isinstance(d, list) and d:
        d = d[0]
    if not isinstance(d, dict):
        d = {}

    return {
        "ticker":   ticker.upper(),
        "gamma":    _safe_float(d.get("gamma") or d.get("total_gamma")) or 0,
        "delta":    _safe_float(d.get("delta") or d.get("total_delta")) or 0,
        "call_gex": _safe_float(d.get("call_gex") or d.get("gamma_call")) or 0,
        "put_gex":  _safe_float(d.get("put_gex")  or d.get("gamma_put"))  or 0,
        "charm":    _safe_float(d.get("charm")) or 0,
        "vanna":    _safe_float(d.get("vanna")) or 0,
    }


# ─────────────────────────────────────────────────────────────
# Market Tide
# ─────────────────────────────────────────────────────────────

def get_market_flow_summary() -> dict:
    """Market-wide options sentiment."""
    data = _get("/api/market/market-tide")

    if not data or isinstance(data, dict) and "_error" in data:
        return {"_error": data.get("_error", "No data") if data else "No data"}

    d = data.get("data", data) if isinstance(data, dict) else {}
    if isinstance(d, list) and d:
        d = d[0]
    if not isinstance(d, dict):
        d = {}

    call_prem = _safe_float(d.get("call_premium") or d.get("bulls_premium")) or 0
    put_prem  = _safe_float(d.get("put_premium")  or d.get("bears_premium")) or 0
    net       = call_prem - put_prem

    return {
        "call_premium": call_prem,
        "put_premium":  put_prem,
        "net_premium":  net,
        "sentiment":    "Bullish 🐂" if net > 0 else "Bearish 🐻",
        "call_volume":  int(_safe_float(d.get("call_volume")) or 0),
        "put_volume":   int(_safe_float(d.get("put_volume"))  or 0),
    }


# ─────────────────────────────────────────────────────────────
# Insider Flow
# ─────────────────────────────────────────────────────────────

def get_insider_flow(ticker: str, limit: int = 20) -> list[dict]:
    """Insider transactions for a ticker."""
    data = _get(f"/api/insider/{ticker.upper()}/ticker-flow", {"limit": limit})

    if not data or isinstance(data, dict) and "_error" in data:
        return [{"_error": data.get("_error", "No data") if data else "No data"}]

    raw = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return []

    results = []
    for r in raw:
        trans = str(r.get("transaction_type") or r.get("type") or "").title()
        shares = int(r.get("shares") or r.get("quantity") or 0)
        price  = _safe_float(r.get("price") or r.get("avg_price")) or 0
        value  = _safe_float(r.get("value") or r.get("total_value")) or (shares * price)
        results.append({
            "date":   str(r.get("date") or r.get("filed_date") or ""),
            "name":   str(r.get("insider_name") or r.get("name") or ""),
            "title":  str(r.get("title") or r.get("position") or ""),
            "type":   trans,
            "shares": shares,
            "price":  price,
            "value":  value,
            "is_buy": any(w in trans.lower() for w in ("buy", "purchase", "acqui")),
        })

    return results


# ─────────────────────────────────────────────────────────────
# Top flow by sector (unused but available)
# ─────────────────────────────────────────────────────────────

def get_top_flow_by_sector(sector: str = "technology") -> list[dict]:
    data = _get("/api/option-trades/flow-alerts", {"sector": sector, "limit": 20})
    if not data or isinstance(data, dict) and "_error" in data:
        return []
    raw = data.get("data", data) if isinstance(data, dict) else data
    return raw if isinstance(raw, list) else []