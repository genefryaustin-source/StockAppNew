"""
modules/market_data/providers/marketdata_provider.py

CHANGES:
- Added MarketDataCreditLimitException and MarketDataRateLimitException,
  matching the pattern already established for Polygon
  (PolygonRateLimitException). Previously every HTTP error >=400,
  including a 429 credit-limit exhaustion, was caught internally and
  silently turned into an empty DataFrame -- indistinguishable from a
  symbol that genuinely has no data. Traced both real callers
  (modules/market_data/service.py, modules/market_data/updater.py --
  confirmed the two others that reference this file,
  provider_registry_legacy.py in two locations and
  options_provider_router.py's unrelated get_chain() usage, are either
  completely orphaned or call a different function entirely) before
  changing this contract.
- MarketDataCreditLimitException is raised specifically when the
  response body contains "credit limit" -- confirmed exact wording
  from a real response ("You've reached your API credit limit for
  your Market Data account"), which is MarketData.app's own account-
  level monthly/daily credit allowance, not a transient rate limit.
  A short cooldown is the wrong response to this; callers should use
  a much longer one.
- MarketDataRateLimitException covers other 429s that don't match
  that specific wording (genuine short-term rate limiting).
- Removed extensive debug print pollution, including printing full
  DataFrame contents (df.head(), df.dtypes) on every single
  successful call.
"""

import logging

import requests
import pandas as pd

from datetime import datetime, UTC
from modules.utils.config import get_secret

logger = logging.getLogger(__name__)


class MarketDataCreditLimitException(Exception):
    """Account-level credit/quota exhausted -- not a short-term rate limit."""
    pass


class MarketDataRateLimitException(Exception):
    """A transient, short-term rate limit (429 without the credit-limit wording)."""
    pass


BASE_URL = "https://api.marketdata.app/v1"


def get_history(
    symbol,
    period="1y",
    start=None,
    end=None,
    interval="1d",
):
    api_key = get_secret("MARKETDATA_API_KEY")

    if not api_key:
        logger.warning("MarketData API key missing")
        return pd.DataFrame()

    symbol = str(symbol).upper().strip()

    # -----------------------------------
    # INTERVAL -> RESOLUTION MAP
    # -----------------------------------
    resolution_map = {
        "1d": "D",
        "1h": "60",
        "30m": "30",
        "15m": "15",
        "5m": "5",
        "1m": "1",
    }

    resolution = resolution_map.get(interval, "D")

    # -----------------------------------
    # DEFAULT DATE RANGE
    # -----------------------------------
    if end is None:
        end = int(datetime.now(UTC).timestamp())

    if start is None:
        # default 1 year
        start = end - (86400 * 365)

    # -----------------------------------
    # MARKETDATA URL
    # -----------------------------------
    url = (
        f"{BASE_URL}/stocks/candles/"
        f"{resolution}/{symbol}/"
    )

    headers = {
        "Authorization": f"Token {api_key}",
        "User-Agent": "Mozilla/5.0",
    }

    params = {
        "from": start,
        "to": end,
    }

    r = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30,
    )

    # -----------------------------------
    # HTTP ERROR
    # -----------------------------------
    if r.status_code >= 400:
        body = r.text[:1000]

        if r.status_code == 429:
            if "credit limit" in body.lower():
                raise MarketDataCreditLimitException(
                    f"MarketData credit limit reached for {symbol}: {body}"
                )
            raise MarketDataRateLimitException(
                f"MarketData rate limited for {symbol}: {body}"
            )

        logger.warning("MarketData HTTP error %s for %s: %s", r.status_code, symbol, body)
        return pd.DataFrame()

    # -----------------------------------
    # JSON PARSE
    # -----------------------------------
    data = r.json()

    if not isinstance(data, dict):
        logger.warning("MarketData invalid JSON for %s", symbol)
        return pd.DataFrame()

    # -----------------------------------
    # STATUS CHECK
    # -----------------------------------
    status = data.get("s")

    if status and status != "ok":
        logger.debug("MarketData status %s for %s", status, symbol)
        return pd.DataFrame()

    # -----------------------------------
    # EXTRACT ARRAYS
    # -----------------------------------
    timestamps = data.get("t", [])
    opens = data.get("o", [])
    highs = data.get("h", [])
    lows = data.get("l", [])
    closes = data.get("c", [])
    volumes = data.get("v", [])

    count = min(
        len(timestamps),
        len(opens),
        len(highs),
        len(lows),
        len(closes),
        len(volumes),
    )

    if count == 0:
        logger.debug("MarketData empty series for %s", symbol)
        return pd.DataFrame()

    # -----------------------------------
    # BUILD ROWS
    # -----------------------------------
    rows = []

    for i in range(count):
        rows.append({
            "Date": pd.to_datetime(timestamps[i], unit="s"),
            "Open": float(opens[i]),
            "High": float(highs[i]),
            "Low": float(lows[i]),
            "Close": float(closes[i]),
            "Volume": float(volumes[i]),
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return pd.DataFrame()

    # -----------------------------------
    # SORT
    # -----------------------------------
    df = df.sort_values("Date")

    # -----------------------------------
    # NORMALIZE
    # -----------------------------------
    from modules.market_data.service import (
        _normalize_df,
    )

    df = _normalize_df(df)

    return df