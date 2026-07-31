"""
modules/market_data/providers/finnhub_provider.py

CHANGES:
- Added FinnhubAccessException, matching the pattern already
  established for MarketData (MarketDataCreditLimitException) and
  Polygon (PolygonRateLimitException). Previously every HTTP error,
  including a 403 "You don't have access to this resource" (a
  permanent plan/permission issue, not a transient rate limit), was
  caught internally and silently returned as None -- indistinguishable
  from a symbol that genuinely has no data. Confirmed from real logs:
  without a dedicated long cooldown, the router's consecutive-failure
  counter climbed indefinitely (3, 4, 5... 40+) as the provider was
  retried roughly every 2 minutes for the entire run, since a 403
  access error will never resolve on retry the way a transient rate
  limit might.
- Removed debug print() pollution in favor of logging.
"""

from __future__ import annotations

import logging

import pandas as pd
import requests

from datetime import datetime, UTC, timedelta

logger = logging.getLogger(__name__)


class FinnhubAccessException(Exception):
    """403 -- account/plan doesn't have access to this resource. Not transient."""
    pass


BASE_URL = "https://finnhub.io/api/v1"


# ---------------------------------------------------
# GET HISTORY
# ---------------------------------------------------

def get_history(
    symbol,
    period="1y",
    start=None,
    end=None,
    interval="D",
):
    resolution_map = {
        "1d": "D",
        "D": "D",
        "1h": "60",
        "5m": "5",
    }

    resolution = resolution_map.get(interval, "D")

    from modules.admin.tenant_api_keys import get_provider_key
    key = get_provider_key("FINNHUB_API_KEY")

    if not key:
        logger.warning("Finnhub API key missing")
        return None

    if end is None:
        end = int(datetime.now(UTC).timestamp())

    if start is None:
        start = int((datetime.now(UTC) - timedelta(days=365)).timestamp())

    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": start,
        "to": end,
        "token": key,
    }

    r = requests.get(
        f"{BASE_URL}/stock/candle",
        params=params,
        timeout=20,
    )

    if r.status_code == 403:
        raise FinnhubAccessException(
            f"Finnhub access denied for {symbol}: {r.text[:200]}"
        )

    if r.status_code != 200:
        logger.warning("Finnhub status error %s for %s: %s", r.status_code, symbol, r.text[:200])
        return None

    data = r.json()

    if data.get("s") != "ok":
        return None

    df = pd.DataFrame({
        "Date": pd.to_datetime(data["t"], unit="s", utc=True),
        "Open": data["o"],
        "High": data["h"],
        "Low": data["l"],
        "Close": data["c"],
        "Volume": data["v"],
    })

    if df.empty:
        return None

    return df