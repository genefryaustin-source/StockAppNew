import requests
import pandas as pd
from datetime import datetime, timedelta

def fetch_ohlcv(symbol: str, period: str, interval: str, api_key: str, timeout: int):
    if not api_key:
        raise RuntimeError("Polygon API key missing")

    # basic period->date range
    end = datetime.utcnow().date()
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
        raise RuntimeError(f"Polygon failed: {j}")

    df = pd.DataFrame(j["results"])
    df["Date"] = pd.to_datetime(df["t"], unit="ms")
    df.rename(columns={"o":"Open","h":"High","l":"Low","c":"Close","v":"Volume"}, inplace=True)
    return df[["Date","Open","High","Low","Close","Volume"]]