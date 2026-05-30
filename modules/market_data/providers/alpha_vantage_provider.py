import requests
import pandas as pd
import time

from datetime import datetime, UTC
from modules.utils.config import get_secret


BASE_URL = "https://www.alphavantage.co/query"

_LAST_ALPHA_CALL = 0.0


def get_history(
        symbol,
        period="1y",
        start=None,
        end=None,
        interval="1d",
):

    api_key = get_secret(
        "ALPHAVANTAGE_API_KEY"
    )

    if not api_key:

        print("❌ ALPHA API KEY MISSING")

        return pd.DataFrame()

    symbol = str(symbol).upper().strip()

    # -----------------------------------
    # FUNCTION MAP
    # -----------------------------------
    if interval == "1d":

        function = "TIME_SERIES_DAILY_ADJUSTED"

    elif interval == "1h":

        function = "TIME_SERIES_INTRADAY"

    else:

        function = "TIME_SERIES_DAILY_ADJUSTED"

    # -----------------------------------
    # PARAMS
    # -----------------------------------
    params = {
        "function": function,
        "symbol": symbol,
        "outputsize": "full",
        "apikey": api_key,
    }

    # -----------------------------------
    # INTRADAY INTERVAL
    # -----------------------------------
    if function == "TIME_SERIES_INTRADAY":

        params["interval"] = "60min"

    # -----------------------------------
    # RATE LIMIT
    # -----------------------------------
    global _LAST_ALPHA_CALL

    elapsed = time.time() - _LAST_ALPHA_CALL

    # Alpha free tier:
    # 5 calls/minute
    if elapsed < 12:

        sleep_for = 12 - elapsed

        print(
            f"⏳ ALPHA RATE LIMIT SLEEP: "
            f"{sleep_for:.2f}s"
        )

        time.sleep(sleep_for)

    _LAST_ALPHA_CALL = time.time()

    try:

        print(
            f"🔥 ALPHA REQUEST: "
            f"{symbol} "
            f"{interval}"
        )

        r = requests.get(
            BASE_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
        )

        # -----------------------------------
        # HTTP ERROR
        # -----------------------------------
        if r.status_code >= 400:

            print(
                f"❌ ALPHA HTTP ERROR "
                f"{symbol}: {r.status_code}"
            )

            print(r.text[:1000])

            return pd.DataFrame()

        # -----------------------------------
        # JSON
        # -----------------------------------
        data = r.json()

        # -----------------------------------
        # RATE LIMIT
        # -----------------------------------
        if "Note" in data:

            print("⚠️ ALPHA RATE LIMITED")

            return pd.DataFrame()

        # -----------------------------------
        # ERROR MESSAGE
        # -----------------------------------
        if "Error Message" in data:

            print(
                f"❌ ALPHA API ERROR: "
                f"{symbol}"
            )

            print(data["Error Message"])

            return pd.DataFrame()

        # -----------------------------------
        # TIME SERIES KEY
        # -----------------------------------
        ts = None

        if "Time Series (Daily)" in data:

            ts = data.get(
                "Time Series (Daily)"
            )

        elif "Time Series (60min)" in data:

            ts = data.get(
                "Time Series (60min)"
            )

        if not ts:

            print(
                f"⚠️ ALPHA EMPTY TS: "
                f"{symbol}"
            )

            return pd.DataFrame()

        # -----------------------------------
        # BUILD ROWS
        # -----------------------------------
        rows = []

        for dt, vals in ts.items():

            try:

                rows.append({
                    "Date": pd.to_datetime(dt),

                    "Open": float(
                        vals.get("1. open", 0)
                    ),

                    "High": float(
                        vals.get("2. high", 0)
                    ),

                    "Low": float(
                        vals.get("3. low", 0)
                    ),

                    "Close": float(
                        vals.get("4. close", 0)
                    ),

                    "Volume": float(
                        vals.get("6. volume", 0)
                    ),
                })

            except Exception:
                continue

        # -----------------------------------
        # DATAFRAME
        # -----------------------------------
        df = pd.DataFrame(rows)

        if df.empty:

            print(
                f"⚠️ ALPHA DF EMPTY: "
                f"{symbol}"
            )

            return pd.DataFrame()

        # -----------------------------------
        # DATE FILTER
        # -----------------------------------
        if start:

            start_dt = pd.to_datetime(
                start,
                unit="s",
                utc=True,
            )

            df = df[
                df["Date"] >= start_dt
            ]

        if end:

            end_dt = pd.to_datetime(
                end,
                unit="s",
                utc=True,
            )

            df = df[
                df["Date"] <= end_dt
            ]

        # -----------------------------------
        # SORT
        # -----------------------------------
        df = df.sort_values("Date")

        # -----------------------------------
        # DEBUG
        # -----------------------------------
        print(
            f"✅ ALPHA SUCCESS: "
            f"{symbol}"
        )

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

        print(
            f"✅ ALPHA NORMALIZED: "
            f"{symbol}"
        )

        print(df.head())

        print(df.columns.tolist())

        print(df.dtypes)

        print(
            f"NORMALIZED ROWS: "
            f"{len(df)}"
        )

        return df

    except Exception as e:

        print(
            f"❌ ALPHA HISTORY ERROR: "
            f"{symbol} -> {e}"
        )

        return pd.DataFrame()