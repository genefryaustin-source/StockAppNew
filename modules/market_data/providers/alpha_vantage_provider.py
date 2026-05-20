import requests
import pandas as pd
import time
from modules.utils.config import get_secret


BASE_URL = "https://www.alphavantage.co/query"

_LAST_ALPHA_CALL = 0.0


def get_history(symbol: str):

    api_key = get_secret("ALPHAVANTAGE_API_KEY")

    if not api_key:
        return pd.DataFrame()

    symbol = str(symbol).upper().strip()

    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "compact",
        "apikey": api_key,
    }
    global _LAST_ALPHA_CALL

    elapsed = time.time() - _LAST_ALPHA_CALL

    if elapsed < 12:
        time.sleep(12 - elapsed)

    _LAST_ALPHA_CALL = time.time()
    try:

        r = requests.get(
            BASE_URL,
            params=params,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if r.status_code != 200:
            print(f"ALPHA ERROR {symbol}: {r.status_code}")
            return pd.DataFrame()

        data = r.json()
        if "Note" in data:
            print("ALPHA RATE LIMITED")
            return pd.DataFrame()
        ts = data.get("Time Series (Daily)")

        if not ts:
            print(f"ALPHA EMPTY TS: {symbol}")
            return pd.DataFrame()

        rows = []

        for dt, vals in ts.items():

            rows.append({
                "Date": pd.to_datetime(dt),
                "Open": float(vals["1. open"]),
                "High": float(vals["2. high"]),
                "Low": float(vals["3. low"]),
                "Close": float(vals["4. close"]),
                "Volume": float(vals["6. volume"]),
            })

        df = pd.DataFrame(rows)

        from modules.market_data.service import _normalize_df

        return _normalize_df(df)

    except Exception as e:

        print("ALPHA HISTORY ERROR:", symbol, e)

        return pd.DataFrame()