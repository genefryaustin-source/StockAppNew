from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from datetime import datetime, UTC


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

    key = st.secrets.get("TWELVEDATA_API_KEY")

    if not key:
        print("TWELVEDATA API KEY MISSING")
        return pd.DataFrame()

    try:
        # -----------------------------------
        # Normalize intervals
        # -----------------------------------

        interval_map = {
            "1d": "1day",
            "1h": "1h",
            "5m": "5min",
            "15m": "15min",
            "30m": "30min",
        }

        interval = interval_map.get(
            interval,
            "1day",
        )
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
        print("TWELVEDATA URL:", r.url)
        print("TWELVEDATA STATUS:", r.status_code)

        try:
            print("TWELVEDATA CONNECTED:")
        except Exception:
            print("TWELVEDATA TEXT:", r.text)
        if r.status_code != 200:

            print(
                "TWELVEDATA STATUS ERROR",
                r.status_code,
                r.text[:200],
            )

            return pd.DataFrame()

        data = r.json()

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

        numeric_cols = [
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
        ]

        for col in numeric_cols:

            if col in df.columns:

                df[col] = pd.to_numeric(
                    df[col],
                    errors="coerce",
                )

        df = df.sort_values("Date")

        return df

    except Exception as e:

        print(
            "TWELVEDATA ERROR",
            symbol,
            e,
        )

        return pd.DataFrame()