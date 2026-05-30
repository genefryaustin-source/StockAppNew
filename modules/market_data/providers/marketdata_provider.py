import requests
import pandas as pd

from datetime import datetime, UTC
from modules.utils.config import get_secret


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
        print("❌ MARKETDATA API KEY MISSING")
        return pd.DataFrame()

    symbol = str(symbol).upper().strip()

    # -----------------------------------
    # INTERVAL → RESOLUTION MAP
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

    try:

        print(
            f"🔥 MARKETDATA REQUEST: "
            f"{symbol} "
            f"{resolution} "
            f"{start} -> {end}"
        )

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

            print(
                f"❌ MARKETDATA HTTP ERROR "
                f"{symbol}: {r.status_code}"
            )

            print(r.text[:1000])

            return pd.DataFrame()

        # -----------------------------------
        # JSON PARSE
        # -----------------------------------
        data = r.json()

        if not isinstance(data, dict):

            print(
                f"❌ MARKETDATA INVALID JSON: "
                f"{symbol}"
            )

            return pd.DataFrame()

        # -----------------------------------
        # STATUS CHECK
        # -----------------------------------
        status = data.get("s")

        if status and status != "ok":

            print(
                f"❌ MARKETDATA STATUS FAIL: "
                f"{symbol} -> {status}"
            )

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

            print(
                f"⚠️ MARKETDATA EMPTY SERIES: "
                f"{symbol}"
            )

            return pd.DataFrame()

        # -----------------------------------
        # BUILD ROWS
        # -----------------------------------
        rows = []

        for i in range(count):

            rows.append({
                "Date": pd.to_datetime(
                    timestamps[i],
                    unit="s",
                ),
                "Open": float(opens[i]),
                "High": float(highs[i]),
                "Low": float(lows[i]),
                "Close": float(closes[i]),
                "Volume": float(volumes[i]),
            })

        df = pd.DataFrame(rows)

        if df.empty:

            print(
                f"⚠️ MARKETDATA DF EMPTY: "
                f"{symbol}"
            )

            return pd.DataFrame()

        # -----------------------------------
        # SORT
        # -----------------------------------
        df = df.sort_values("Date")

        # -----------------------------------
        # DEBUG
        # -----------------------------------
        print(f"✅ MARKETDATA SUCCESS: {symbol}")
        print(df.head())
        print(df.columns.tolist())
        print(df.dtypes)
        print(f"ROWS: {len(df)}")

        # -----------------------------------
        # NORMALIZE
        # -----------------------------------
        from modules.market_data.service import (
            _normalize_df,
        )

        df = _normalize_df(df)

        print(f"✅ NORMALIZED DF: {symbol}")
        print(df.head())
        print(df.columns.tolist())
        print(df.dtypes)
        print(f"NORMALIZED ROWS: {len(df)}")

        return df

    except Exception as e:

        print(
            f"❌ MARKETDATA HISTORY ERROR: "
            f"{symbol} -> {e}"
        )

        return pd.DataFrame()