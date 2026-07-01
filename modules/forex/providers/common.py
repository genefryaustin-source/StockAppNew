"""
modules/forex/providers/common.py

Shared Forex provider utilities.

Sprint 25 Phase 4.5B:
- Standardized quote helpers
- Standardized historical OHLCV helpers
- Requests session with retries
- Provider-safe date/interval normalization
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from functools import lru_cache
from typing import Any, Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

LOGGER = logging.getLogger("forex.providers")

DEFAULT_TIMEOUT = 20
USER_AGENT = "StockApp Forex/1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def normalize_pair(pair: str) -> tuple[str, str, str]:
    p = str(pair or "").upper().replace("-", "/").replace("_", "/").replace(" ", "").strip()
    if "/" in p:
        b, q = p.split("/", 1)
    else:
        b, q = p[:3], p[3:6]
    return b[:3], q[:3], f"{b[:3]}/{q[:3]}"


def pair_symbol(pair: str) -> str:
    _, _, normalized = normalize_pair(pair)
    return normalized.replace("/", "")


def parse_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return utc_now().date()
    return datetime.fromisoformat(str(value)[:10]).date()


def epoch_seconds(value: Any) -> int:
    d = parse_date(value)
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def provider_headers(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    h = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if extra:
        h.update(extra)
    return h


@lru_cache(maxsize=1)
def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update(provider_headers())
    return s


def request_json(url: str, *, params: Optional[dict[str, Any]] = None, headers: Optional[dict[str, str]] = None, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    r = session().get(url, params=params, headers=headers or {}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def env_key(*names: str) -> str:
    for n in names:
        v = os.getenv(n)
        if v:
            return v.strip()
    return ""


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace(",", "").strip()
            if value in {"", "-", "—", "None", "nan"}:
                return default
        return float(value)
    except Exception:
        return default


def normalize_quote(provider: str, pair: str, rate: float, raw: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    base, quote, normalized = normalize_pair(pair)
    return {
        "pair": normalized,
        "symbol": normalized.replace("/", ""),
        "base": base,
        "quote": quote,
        "mid": float(rate),
        "last": float(rate),
        "provider": provider,
        "source": provider,
        "timestamp": utc_iso(),
        "raw": raw or {},
    }


def provider_error(provider: str, message: str, raw: Optional[dict[str, Any]] = None, pair: Optional[str] = None) -> dict[str, Any]:
    payload = {
        "provider": provider,
        "error": message,
        "timestamp": utc_iso(),
        "raw": raw or {},
    }
    if pair:
        _, _, normalized = normalize_pair(pair)
        payload["pair"] = normalized
        payload["symbol"] = normalized.replace("/", "")
    return payload


def normalize_interval(interval: str) -> str:
    text = str(interval or "1day").lower().strip()
    aliases = {
        "daily": "1day", "day": "1day", "1d": "1day", "d": "1day",
        "hour": "1hour", "1h": "1hour", "60min": "1hour",
        "minute": "1min", "1m": "1min",
    }
    return aliases.get(text, text)


def polygon_timespan(interval: str) -> tuple[int, str]:
    interval = normalize_interval(interval)
    if interval in {"1day", "day"}:
        return 1, "day"
    if interval in {"1hour", "hour"}:
        return 1, "hour"
    if interval in {"1min", "minute"}:
        return 1, "minute"
    if interval.endswith("min"):
        return int(interval.replace("min", "") or 1), "minute"
    if interval.endswith("hour"):
        return int(interval.replace("hour", "") or 1), "hour"
    return 1, "day"


def twelvedata_interval(interval: str) -> str:
    interval = normalize_interval(interval)
    mapping = {"1day": "1day", "1hour": "1h", "1min": "1min", "5min": "5min", "15min": "15min", "30min": "30min"}
    return mapping.get(interval, "1day")


def yahoo_interval(interval: str) -> str:
    interval = normalize_interval(interval)
    mapping = {"1day": "1d", "1hour": "1h", "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m"}
    return mapping.get(interval, "1d")


def alpha_vantage_function(interval: str) -> tuple[str, dict[str, Any]]:
    interval = normalize_interval(interval)
    if interval == "1day":
        return "FX_DAILY", {"outputsize": "full"}
    if interval in {"1hour", "60min"}:
        return "FX_INTRADAY", {"interval": "60min", "outputsize": "full"}
    if interval in {"1min", "5min", "15min", "30min"}:
        return "FX_INTRADAY", {"interval": interval, "outputsize": "full"}
    return "FX_DAILY", {"outputsize": "full"}


def build_history_row(*, provider: str, pair: str, asof: Any, open_: Any = None, high: Any = None, low: Any = None, close: Any = None, volume: Any = None, interval: str = "1day", raw: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    base, quote, normalized = normalize_pair(pair)
    close_f = safe_float(close)
    if close_f is None or close_f <= 0:
        return None
    asof_dt: Any = asof
    if isinstance(asof, (int, float)):
        ts = float(asof) / 1000.0 if float(asof) > 10_000_000_000 else float(asof)
        asof_dt = datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    elif isinstance(asof, str):
        try:
            asof_dt = datetime.fromisoformat(asof.replace("Z", "+00:00"))
            if asof_dt.tzinfo is not None:
                asof_dt = asof_dt.astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            d = parse_date(asof)
            asof_dt = datetime(d.year, d.month, d.day)
    elif isinstance(asof, date) and not isinstance(asof, datetime):
        asof_dt = datetime(asof.year, asof.month, asof.day)
    return {
        "pair": normalized,
        "symbol": normalized.replace("/", ""),
        "base": base,
        "quote": quote,
        "asof": asof_dt,
        "open": safe_float(open_, close_f),
        "high": safe_float(high, close_f),
        "low": safe_float(low, close_f),
        "close": close_f,
        "volume": safe_float(volume, 0.0),
        "provider": provider,
        "source": provider,
        "interval": normalize_interval(interval),
        "raw": raw or {},
    }


def history_payload(*, provider: str, pair: str, rows: Iterable[dict[str, Any]], interval: str = "1day", raw: Optional[dict[str, Any]] = None, error: Optional[str] = None) -> dict[str, Any]:
    _, _, normalized = normalize_pair(pair)
    clean_rows = [r for r in rows if isinstance(r, dict)]
    return {
        "status": "ERROR" if error else "OK",
        "provider": provider,
        "pair": normalized,
        "symbol": normalized.replace("/", ""),
        "interval": normalize_interval(interval),
        "rows": clean_rows,
        "row_count": len(clean_rows),
        "error": error,
        "timestamp": utc_iso(),
        "raw": raw or {},
    }
