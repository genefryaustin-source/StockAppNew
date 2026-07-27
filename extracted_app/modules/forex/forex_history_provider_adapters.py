"""
modules/forex/forex_history_provider_adapters.py

Provider-specific historical FX fetchers used by the existing ForexProviderRouter.
These functions do not persist to the database. They return normalized row dictionaries.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import requests


def normalize_pair(pair: Any) -> str:
    value = str(pair or "").upper().strip().replace("/", "").replace("-", "").replace("_", "")
    if len(value) >= 6:
        return f"{value[:3]}/{value[3:6]}"
    return value


def split_pair(pair: Any) -> tuple[str, str]:
    pair = normalize_pair(pair)
    if "/" in pair:
        base, quote = pair.split("/", 1)
        return base[:3], quote[:3]
    return pair[:3], pair[3:6]


def _date_str(value: Any) -> str:
    if value is None:
        return datetime.now(timezone.utc).date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def _unix(value: Any) -> int:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _headers() -> dict[str, str]:
    return {"User-Agent": "StockApp Forex/1.0", "Accept": "application/json"}


def polygon_history(pair: str, start_date: Any, end_date: Any, interval: str = "1day") -> dict:
    key = os.getenv("POLYGON_API_KEY") or os.getenv("POLYGON_KEY") or ""
    if not key:
        return {"provider": "polygon_fx", "error": "Polygon API key not configured", "rows": []}
    base, quote = split_pair(pair)
    ticker = f"C:{base}{quote}"
    multiplier = 1
    timespan = "day"
    if interval in {"1hour", "hour", "60min"}:
        timespan = "hour"
    elif interval in {"1min", "minute"}:
        timespan = "minute"
    url = f"https://api.polygon.io/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{_date_str(start_date)}/{_date_str(end_date)}"
    r = requests.get(url, params={"adjusted": "true", "sort": "asc", "limit": 50000, "apikey": key}, timeout=30, headers=_headers())
    r.raise_for_status()
    data = r.json()
    if data.get("status") not in {"OK", "DELAYED"} and not data.get("results"):
        return {"provider": "polygon_fx", "error": data.get("error") or data.get("message") or "Polygon returned no history", "raw": data, "rows": []}
    rows = []
    for row in data.get("results") or []:
        ts = row.get("t")
        asof = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).replace(tzinfo=None) if ts else None
        rows.append({
            "pair": normalize_pair(pair), "symbol": normalize_pair(pair).replace("/", ""), "asof": asof,
            "open": row.get("o"), "high": row.get("h"), "low": row.get("l"), "close": row.get("c"),
            "volume": row.get("v"), "vwap": row.get("vw"), "provider": "polygon_fx", "source": "polygon",
        })
    return {"provider": "polygon_fx", "rows": rows, "raw": {"status": data.get("status"), "resultsCount": data.get("resultsCount")}}


def twelvedata_history(pair: str, start_date: Any, end_date: Any, interval: str = "1day") -> dict:
    key = os.getenv("TWELVEDATA_API_KEY") or os.getenv("TWELVEDATA_KEY") or ""
    if not key:
        return {"provider": "twelvedata_fx", "error": "TwelveData API key not configured", "rows": []}
    base, quote = split_pair(pair)
    td_interval = {"1day": "1day", "day": "1day", "1hour": "1h", "hour": "1h", "1min": "1min"}.get(interval, interval)
    r = requests.get(
        "https://api.twelvedata.com/time_series",
        params={"symbol": f"{base}/{quote}", "interval": td_interval, "start_date": _date_str(start_date), "end_date": _date_str(end_date), "apikey": key, "outputsize": 5000, "order": "ASC"},
        timeout=30,
        headers=_headers(),
    )
    r.raise_for_status()
    data = r.json()
    if data.get("status") == "error":
        return {"provider": "twelvedata_fx", "error": data.get("message", "TwelveData returned error"), "raw": data, "rows": []}
    rows = []
    for row in data.get("values") or []:
        rows.append({
            "pair": normalize_pair(pair), "symbol": normalize_pair(pair).replace("/", ""), "asof": row.get("datetime"),
            "open": row.get("open"), "high": row.get("high"), "low": row.get("low"), "close": row.get("close"),
            "volume": row.get("volume"), "provider": "twelvedata_fx", "source": "twelvedata",
        })
    return {"provider": "twelvedata_fx", "rows": rows, "raw": {"status": data.get("status"), "meta": data.get("meta")}}


def alpha_vantage_history(pair: str, start_date: Any, end_date: Any, interval: str = "1day") -> dict:
    key = os.getenv("ALPHA_VANTAGE_API_KEY") or os.getenv("ALPHAVANTAGE_API_KEY") or os.getenv("ALPHA_VANTAGE_KEY") or ""
    if not key:
        return {"provider": "alpha_vantage_fx", "error": "Alpha Vantage API key not configured", "rows": []}
    base, quote = split_pair(pair)
    function = "FX_DAILY"
    params = {"function": function, "from_symbol": base, "to_symbol": quote, "outputsize": "full", "apikey": key}
    r = requests.get("https://www.alphavantage.co/query", params=params, timeout=30, headers=_headers())
    r.raise_for_status()
    data = r.json()
    series = data.get("Time Series FX (Daily)") or {}
    if not series:
        return {"provider": "alpha_vantage_fx", "error": data.get("Note") or data.get("Error Message") or "Alpha Vantage returned no daily FX series", "raw": data, "rows": []}
    start_s, end_s = _date_str(start_date), _date_str(end_date)
    rows = []
    for day, row in sorted(series.items()):
        if day < start_s or day > end_s:
            continue
        rows.append({
            "pair": normalize_pair(pair), "symbol": normalize_pair(pair).replace("/", ""), "asof": day,
            "open": row.get("1. open"), "high": row.get("2. high"), "low": row.get("3. low"), "close": row.get("4. close"),
            "provider": "alpha_vantage_fx", "source": "alpha_vantage",
        })
    return {"provider": "alpha_vantage_fx", "rows": rows, "raw": {"rows": len(rows)}}


def yahoo_history(pair: str, start_date: Any, end_date: Any, interval: str = "1day") -> dict:
    base, quote = split_pair(pair)
    yahoo_symbol = f"{base}{quote}=X"
    y_interval = {"1day": "1d", "day": "1d", "1hour": "1h", "hour": "1h", "1min": "1m"}.get(interval, "1d")
    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}",
        params={"period1": _unix(start_date), "period2": _unix(end_date) + 86400, "interval": y_interval},
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    r.raise_for_status()
    data = r.json()
    try:
        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp") or []
        quote_data = (result.get("indicators") or {}).get("quote") or [{}]
        q = quote_data[0]
    except Exception:
        return {"provider": "yahoo_fx", "error": "Yahoo returned no usable history", "raw": data, "rows": []}
    rows = []
    for i, ts in enumerate(timestamps):
        close = (q.get("close") or [None])[i]
        if close is None:
            continue
        rows.append({
            "pair": normalize_pair(pair), "symbol": normalize_pair(pair).replace("/", ""),
            "asof": datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None),
            "open": (q.get("open") or [None])[i], "high": (q.get("high") or [None])[i],
            "low": (q.get("low") or [None])[i], "close": close,
            "volume": (q.get("volume") or [None])[i], "provider": "yahoo_fx", "source": "yahoo",
        })
    return {"provider": "yahoo_fx", "rows": rows, "raw": {"rows": len(rows)}}


HISTORY_ADAPTERS = {
    "polygon_fx": polygon_history,
    "twelvedata_fx": twelvedata_history,
    "alpha_vantage_fx": alpha_vantage_history,
    "yahoo_fx": yahoo_history,
}
