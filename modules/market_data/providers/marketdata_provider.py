import requests
import pandas as pd
import time

from modules.utils.config import get_secret


BASE_URL = "https://api.marketdata.app/v1"


def get_history(
        symbol: str,
        timeframe: str = "1D",
        limit: int = 500,
):

    api_key = get_secret("MARKETDATA_API_KEY")

    if not api_key:
        return pd.DataFrame()

    symbol = str(symbol).upper().strip()

    url = f"{BASE_URL}/stocks/candles/{timeframe}/{symbol}/"

    headers = {
        "Authorization": f"Token {api_key}",
        "User-Agent": "Mozilla/5.0",
    }

    params = {
        "limit": limit
    }

    try:

        r = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=20,
        )

        if r.status_code != 200:
            print(f"MARKETDATA ERROR {symbol}: {r.status_code}")
            print(r.text[:500])
            return pd.DataFrame()

        data = r.json()

        if not isinstance(data, dict):
            return pd.DataFrame()

        if "s" in data and data["s"] != "ok":
            print(f"MARKETDATA STATUS FAIL: {symbol}")
            return pd.DataFrame()

        rows = []

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

        df = df.sort_values("Date")

        from modules.market_data.service import _normalize_df

        return _normalize_df(df)

    except Exception as e:

        print("MARKETDATA HISTORY ERROR:", symbol, e)

        return pd.DataFrame()