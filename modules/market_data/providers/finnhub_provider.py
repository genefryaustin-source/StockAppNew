from __future__ import annotations

import pandas as pd
import requests
import streamlit as st

from datetime import datetime, UTC, timedelta


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

    resolution = resolution_map.get(
        interval,
        "D",
    )
    key = st.secrets.get("FINNHUB_API_KEY")

    if not key:
        print("FINNHUB API KEY MISSING")
        return None

    try:

        if end is None:
            end = int(datetime.now(UTC).timestamp())

        if start is None:
            start = int(
                (
                    datetime.now(UTC)
                    - timedelta(days=365)
                ).timestamp()
            )

        resolution_map = {
            "1d": "D",
            "D": "D",
            "1h": "60",
            "5m": "5",
        }

        resolution = resolution_map.get(
            interval,
            "D",
        )

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

        if r.status_code != 200:

            print(
                "FINNHUB STATUS ERROR",
                r.status_code,
                r.text[:200],
            )

            return None

        data = r.json()

        if data.get("s") != "ok":
            return None

        df = pd.DataFrame({
            "Date": pd.to_datetime(
                data["t"],
                unit="s",
                utc=True,
            ),
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"],
        })

        if df.empty:
            return None

        return df

    except Exception as e:

        print(
            "FINNHUB ERROR",
            symbol,
            e,
        )

        return None