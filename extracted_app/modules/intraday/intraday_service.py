"""
modules/intraday/intraday_service.py

Intraday / multi-timeframe chart data service.

Uses existing providers in priority order:
  1. MarketData.app  — /v1/stocks/candles/{resolution}/{symbol}/
     Already supports 1m, 5m, 15m, 30m, 1h natively
  2. Polygon          — /v2/aggs/ticker/{symbol}/range/{mult}/{timespan}/
     Already supports minute/hour timeframes
  3. Alpaca           — /v2/stocks/{symbol}/bars
     Free plan supports 15-min delayed intraday

Date range logic per timeframe:
  1m  → last 2 trading days (API limits)
  5m  → last 5 trading days
  15m → last 10 trading days
  30m → last 20 trading days
  1h  → last 60 trading days
  1d  → last 365 days (existing)
  1w  → last 3 years
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st


# ─────────────────────────────────────────────────────────────
# Timeframe config
# ─────────────────────────────────────────────────────────────

TIMEFRAMES = {
    "1m":  {"label": "1 Min",   "days_back": 2,   "max_bars": 390*2},
    "5m":  {"label": "5 Min",   "days_back": 5,   "max_bars": 78*5},
    "15m": {"label": "15 Min",  "days_back": 10,  "max_bars": 26*10},
    "30m": {"label": "30 Min",  "days_back": 20,  "max_bars": 13*20},
    "1h":  {"label": "1 Hour",  "days_back": 60,  "max_bars": 7*60},
    "4h":  {"label": "4 Hour",  "days_back": 120, "max_bars": 2*120},
    "1d":  {"label": "Daily",   "days_back": 365, "max_bars": 365},
    "1w":  {"label": "Weekly",  "days_back": 1095,"max_bars": 156},
}

_CACHE: dict = {}
_CACHE_TTL = {
    "1m":  30,    # 30 seconds
    "5m":  60,    # 1 minute
    "15m": 120,
    "30m": 300,
    "1h":  600,
    "4h":  1800,
    "1d":  3600,
    "1w":  86400,
}


def _get_secret(key: str) -> Optional[str]:
    try:
        if key in st.secrets:
            return str(st.secrets[key]) or None
        # Check nested secrets
        for section in ["market_data", "trading", "alpaca"]:
            try:
                val = st.secrets.get(section, {}).get(key, "")
                if val:
                    return str(val)
            except Exception:
                pass
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


def _date_range(interval: str) -> tuple[str, str]:
    """Return (start_date, end_date) strings for a given interval."""
    cfg = TIMEFRAMES.get(interval, TIMEFRAMES["1d"])
    now   = datetime.now(timezone.utc)
    start = now - timedelta(days=cfg["days_back"])
    return start.strftime("%Y-%m-%d"), now.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────
# Provider 1: MarketData.app (primary)
# ─────────────────────────────────────────────────────────────

def _fetch_marketdata(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    key = _get_secret("MARKETDATA_API_KEY")
    if not key:
        return None

    resolution_map = {
        "1m": "1", "5m": "5", "15m": "15", "30m": "30",
        "1h": "60", "4h": "240", "1d": "D", "1w": "W",
    }
    resolution = resolution_map.get(interval)
    if not resolution:
        return None

    start_dt, end_dt = _date_range(interval)
    start_ts = int(datetime.strptime(start_dt, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp())
    end_ts   = int(datetime.strptime(end_dt, "%Y-%m-%d")
                   .replace(tzinfo=timezone.utc).timestamp()) + 86400

    try:
        r = requests.get(
            f"https://api.marketdata.app/v1/stocks/candles/{resolution}/{symbol.upper()}/",
            headers={"Authorization": f"Token {key}", "Accept": "application/json"},
            params={"from": start_ts, "to": end_ts},
            timeout=12,
        )
        if r.status_code not in (200, 203):
            return None

        data = r.json()
        if data.get("s") == "error" or "t" not in data:
            return None

        df = pd.DataFrame({
            "Date":   pd.to_datetime(data["t"], unit="s", utc=True),
            "Open":   data["o"],
            "High":   data["h"],
            "Low":    data["l"],
            "Close":  data["c"],
            "Volume": data["v"],
        })
        df = df.sort_values("Date").reset_index(drop=True)
        return df if not df.empty else None

    except Exception as e:
        print(f"[intraday] MarketData error {symbol} {interval}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Provider 2: Polygon (fallback)
# ─────────────────────────────────────────────────────────────

def _fetch_polygon(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    key = _get_secret("POLYGON_API_KEY") or _get_secret("MASSIVE_API_KEY")
    if not key:
        return None

    timespan_map = {
        "1m": ("minute", 1), "5m": ("minute", 5),
        "15m": ("minute", 15), "30m": ("minute", 30),
        "1h": ("hour", 1), "4h": ("hour", 4),
        "1d": ("day", 1), "1w": ("week", 1),
    }
    if interval not in timespan_map:
        return None

    timespan, multiplier = timespan_map[interval]
    start_dt, end_dt     = _date_range(interval)

    try:
        r = requests.get(
            f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}"
            f"/range/{multiplier}/{timespan}/{start_dt}/{end_dt}",
            params={"apiKey": key, "adjusted": "true", "sort": "asc", "limit": 50000},
            timeout=12,
        )
        if r.status_code != 200:
            return None

        data = r.json()
        results = data.get("results", [])
        if not results:
            return None

        df = pd.DataFrame(results)
        df["Date"] = pd.to_datetime(df["t"], unit="ms", utc=True)
        df.rename(columns={
            "o": "Open", "h": "High", "l": "Low",
            "c": "Close", "v": "Volume",
        }, inplace=True)
        df = df[["Date", "Open", "High", "Low", "Close", "Volume"]].sort_values("Date")
        return df.reset_index(drop=True) if not df.empty else None

    except Exception as e:
        print(f"[intraday] Polygon error {symbol} {interval}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Provider 3: Alpaca (free tier, 15-min delayed)
# ─────────────────────────────────────────────────────────────

def _fetch_alpaca(symbol: str, interval: str) -> Optional[pd.DataFrame]:
    key    = _get_secret("ALPACA_API_KEY")
    secret = _get_secret("ALPACA_API_SECRET")
    if not key or not secret:
        return None

    timeframe_map = {
        "1m": "1Min", "5m": "5Min", "15m": "15Min",
        "30m": "30Min", "1h": "1Hour", "4h": "4Hour",
        "1d": "1Day", "1w": "1Week",
    }
    tf = timeframe_map.get(interval)
    if not tf:
        return None

    start_dt, end_dt = _date_range(interval)

    try:
        r = requests.get(
            f"https://data.alpaca.markets/v2/stocks/{symbol.upper()}/bars",
            headers={
                "APCA-API-KEY-ID":     key,
                "APCA-API-SECRET-KEY": secret,
                "Accept":              "application/json",
            },
            params={
                "timeframe": tf,
                "start":     start_dt + "T00:00:00Z",
                "end":       end_dt   + "T23:59:59Z",
                "limit":     10000,
                "adjustment":"raw",
                "feed":      "iex",  # free tier uses IEX
            },
            timeout=12,
        )
        if r.status_code != 200:
            return None

        data  = r.json()
        bars  = data.get("bars", [])
        if not bars:
            return None

        df = pd.DataFrame(bars)
        df["Date"] = pd.to_datetime(df["t"], utc=True)
        df.rename(columns={
            "o": "Open", "h": "High", "l": "Low",
            "c": "Close", "v": "Volume",
        }, inplace=True)
        cols = ["Date", "Open", "High", "Low", "Close", "Volume"]
        cols = [c for c in cols if c in df.columns]
        return df[cols].sort_values("Date").reset_index(drop=True)

    except Exception as e:
        print(f"[intraday] Alpaca error {symbol} {interval}: {e}")
        return None


# ─────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────

def get_intraday_data(
    symbol: str,
    interval: str = "5m",
    force_refresh: bool = False,
) -> dict:
    """
    Fetch intraday/multi-timeframe OHLCV data.

    Returns:
        {
            "df":       pd.DataFrame with Date/Open/High/Low/Close/Volume,
            "source":   "marketdata" | "polygon" | "alpaca",
            "interval": "5m",
            "symbol":   "NVDA",
            "error":    None | str,
        }
    """
    import time

    cache_key = f"intraday_{symbol}_{interval}"
    ttl       = _CACHE_TTL.get(interval, 300)

    if not force_refresh:
        cached = _CACHE.get(cache_key)
        if cached and time.time() - cached["ts"] < ttl:
            return cached["data"]

    result = {
        "df":       None,
        "source":   None,
        "interval": interval,
        "symbol":   symbol.upper(),
        "error":    None,
    }

    # Try providers in order
    for provider_fn, name in [
        (_fetch_marketdata, "marketdata"),
        (_fetch_polygon,    "polygon"),
        (_fetch_alpaca,     "alpaca"),
    ]:
        df = provider_fn(symbol, interval)
        if df is not None and not df.empty and len(df) > 5:
            result["df"]     = df
            result["source"] = name
            break

    if result["df"] is None:
        result["error"] = (
            f"No intraday data available for {symbol} at {interval}. "
            "MarketData.app, Polygon, and Alpaca all returned no data. "
            "Check that your API keys support intraday data."
        )

    _CACHE[cache_key] = {"data": result, "ts": time.time()}
    return result


def get_available_intervals() -> list[dict]:
    """Return list of available timeframes for UI selector."""
    return [
        {"value": k, "label": v["label"]}
        for k, v in TIMEFRAMES.items()
    ]