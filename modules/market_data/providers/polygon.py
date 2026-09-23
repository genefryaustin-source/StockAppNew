import requests
import pandas as pd
from datetime import datetime, timedelta, UTC

class PolygonRateLimitException(Exception):
    """Raised when Polygon/Massive returns a rate limit response."""
    pass


def fetch_grouped_daily(date: str, api_key: str, timeout: int = 30) -> pd.DataFrame:
    """
    Fetches OHLCV for EVERY US stock in one call via Polygon's "grouped
    daily" endpoint -- counts as a single request against the free tier's
    5-calls/minute limit regardless of how many thousands of tickers come
    back, which is the whole point of using it for a full-universe price
    refresh instead of one call per symbol.

    date: "YYYY-MM-DD". Note Polygon's free tier is end-of-day only, so
    use a date that's already closed (yesterday during market hours,
    today after close) -- requesting today's date mid-session on the free
    tier will come back empty, not wrong, since the bar isn't final yet.

    Returns columns: Symbol, Open, High, Low, Close, Volume -- same
    column names fetch_ohlcv() above uses, so callers can treat both the
    same way. Returns an empty DataFrame (not None) if the endpoint has
    no data for that date (weekend/holiday) or the request fails.
    """
    if not api_key:
        raise RuntimeError("Polygon API key missing")

    # Note: polygon.io rebranded to Massive in 2026 -- the docs/dashboard
    # moved to massive.com, but this api.polygon.io endpoint still works
    # as of this writing. Worth re-verifying if this ever starts failing
    # with a domain-level error rather than an API-level one.
    url = f"https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/{date}"
    r = requests.get(url, params={"apiKey": api_key, "adjusted": "true"}, timeout=timeout)
    j = r.json()

    if "results" not in j or not j["results"]:
        error_text = str(j)
        if "maximum requests per minute" in error_text.lower() or "rate limit" in error_text.lower():
            raise PolygonRateLimitException(error_text)
        return pd.DataFrame(columns=["Symbol", "Open", "High", "Low", "Close", "Volume"])

    df = pd.DataFrame(j["results"])
    df.rename(columns={
        "T": "Symbol", "o": "Open", "h": "High", "l": "Low", "c": "Close", "v": "Volume",
    }, inplace=True)
    return df[["Symbol", "Open", "High", "Low", "Close", "Volume"]]


def fetch_ohlcv(symbol: str, period: str, interval: str, api_key: str, timeout: int):
    if not api_key:
        raise RuntimeError("Polygon API key missing")

    # basic period->date range
    end = datetime.now(UTC).date()
    start = end - timedelta(days=400 if period in ("1y","2y") else 120)
    start_s = start.isoformat()
    end_s = end.isoformat()

    # interval mapping
    if interval.endswith("m"):
        timespan = "minute"
        multiplier = int(interval.replace("m",""))
    elif interval.endswith("h"):
        timespan = "hour"
        multiplier = int(interval.replace("h",""))
    else:
        timespan = "day"
        multiplier = 1

    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_s}/{end_s}"
    r = requests.get(url, params={"apiKey": api_key, "adjusted": "true", "sort": "asc"}, timeout=timeout)
    j = r.json()
    if "results" not in j:
        error_text = str(j)

        if (
                "maximum requests per minute" in error_text.lower()
                or "rate limit" in error_text.lower()
        ):
            raise PolygonRateLimitException(error_text)


    df = pd.DataFrame(j["results"])
    df["Date"] = pd.to_datetime(df["t"], unit="ms")
    df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"}, inplace=True)
    return df[["Date","Open","High","Low","Close","Volume"]]