"""
modules/market_data/providers/twelvedata_provider.py

CHANGES:
- Added TwelveDataRateLimitException, matching the pattern already
  established for MarketData, Polygon, and Finnhub. Previously every
  HTTP error, including a 429, was caught internally and silently
  returned as an empty DataFrame -- indistinguishable from a symbol
  that genuinely has no data, and giving callers no way to apply an
  appropriate cooldown.
- Confirmed TwelveData's exact 429 wording from a real, documented
  occurrence: "You have run out of API credits for the current
  minute" -- and confirmed from TwelveData's own support docs that
  the credit quota resets at the start of every new minute. This is
  a genuinely short-lived, per-minute limit (unlike MarketData's
  credit-limit exception, which is a daily/monthly account-level
  quota deserving a 6-hour cooldown) -- so callers should use a short
  cooldown here (recommended: ~2 minutes), not a long one.
- Removed debug print() pollution in favor of logging.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

logger = logging.getLogger(__name__)


class TwelveDataRateLimitException(Exception):
    """
    429 -- per-minute API credit limit reached. Confirmed from
    TwelveData's own docs that this resets at the start of the next
    minute, so a short cooldown (not a long one) is the correct
    response.
    """
    pass


BASE_URL = "https://api.twelvedata.com"


# ---------------------------------------------------
# GET HISTORY
# ---------------------------------------------------

def get_history(
    symbol,
    period="1y",
    start=None,
    end=None,
    interval="1day",
):
    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("TWELVEDATA_API_KEY")

    if not key:
        logger.warning("TwelveData API key missing")
        return pd.DataFrame()

    interval_map = {
        "1d": "1day",
        "1h": "1h",
        "5m": "5min",
        "15m": "15min",
        "30m": "30min",
    }
    interval = interval_map.get(interval, "1day")

    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": key,
        "format": "JSON",
        "outputsize": 500,
    }

    r = requests.get(
        f"{BASE_URL}/time_series",
        params=params,
        timeout=20,
    )

    if r.status_code == 429:
        body = r.text[:500]
        if "credit" in body.lower() or "per minute" in body.lower():
            raise TwelveDataRateLimitException(
                f"TwelveData per-minute credit limit reached for {symbol}: {body}"
            )
        # A 429 without the confirmed per-minute-credit wording --
        # still a rate limit, but not confirmed to be the specific
        # short-lived case, so let it fall through to the generic
        # handling below rather than assume the short cooldown applies.

    if r.status_code != 200:
        logger.warning("TwelveData status error %s for %s: %s", r.status_code, symbol, r.text[:200])
        return pd.DataFrame()

    data = r.json()

    if data.get("status") == "error":
        logger.debug("TwelveData error for %s: %s", symbol, data.get("message"))
        return pd.DataFrame()

    values = data.get("values")

    if not values:
        return pd.DataFrame()

    df = pd.DataFrame(values)

    if df.empty:
        return pd.DataFrame()

    df.rename(
        columns={
            "datetime": "Date",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )

    df["Date"] = pd.to_datetime(df["Date"])

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("Date")

    return df