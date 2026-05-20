"""
test_finnhub_debug.py

Standalone Finnhub diagnostics + endpoint validation tool.

PURPOSE
-------
This script tests:

1. API key validity
2. Quote endpoint
3. Candle/history endpoint
4. Response JSON parsing
5. Rate limiting
6. Cloudflare/403 behavior
7. Empty body issues
8. Request latency
9. Request headers
10. Bulk symbol stress test

USE
---
python test_finnhub_debug.py

OPTIONAL
--------
Set your key here OR use environment variable:

set FINNHUB_API_KEY=YOUR_KEY

REQUIRES
--------
pip install requests pandas
"""

import os
import time
import json
import traceback
from datetime import datetime, timedelta

import requests
import pandas as pd


# =========================================================
# CONFIG
# =========================================================

import streamlit as st

try:
    API_KEY = st.secrets["FINNHUB_API_KEY"]
except Exception:
    API_KEY = ""

API_KEY = str(API_KEY).strip()

TEST_SYMBOLS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "PLTR",
    "TSLA",
]

BASE_URL = "https://finnhub.io/api/v1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    )
}


# =========================================================
# HELPERS
# =========================================================

def safe_json(resp):
    """
    Safely parse JSON.
    """

    try:

        if resp.status_code != 200:
            print(f"❌ HTTP STATUS: {resp.status_code}")
            print("RESPONSE TEXT:")
            print(resp.text[:500])
            return None

        if not resp.text.strip():
            print("❌ EMPTY RESPONSE BODY")
            return None

        return resp.json()

    except Exception as e:

        print("❌ JSON PARSE ERROR:", e)
        print(resp.text[:1000])

        return None


def request_debug(endpoint, params=None):

    url = f"{BASE_URL}/{endpoint}"

    if params is None:
        params = {}

    params["token"] = API_KEY

    print("\n" + "=" * 80)
    print("REQUEST")
    print("=" * 80)
    print("URL:", url)
    print("PARAMS:", params)

    start = time.time()

    try:

        resp = requests.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=20,
        )

        elapsed = round(time.time() - start, 3)

        print("\nSTATUS:", resp.status_code)
        print("ELAPSED:", elapsed, "sec")

        print("\nHEADERS:")
        for k, v in resp.headers.items():
            print(f"{k}: {v}")

        data = safe_json(resp)

        if data is not None:
            print("\nJSON PREVIEW:")
            print(json.dumps(data, indent=2)[:2000])

        return data

    except Exception as e:

        print("❌ REQUEST FAILED")
        traceback.print_exc()

        return None


# =========================================================
# TESTS
# =========================================================

def test_quote(symbol="AAPL"):

    print("\n🔥 TESTING QUOTE ENDPOINT")

    data = request_debug(
        "quote",
        {
            "symbol": symbol,
        }
    )

    if isinstance(data, dict):
        print("\n✅ QUOTE SUCCESS")

        print("Current Price:", data.get("c"))
        print("Volume:", data.get("v"))

    else:
        print("\n❌ QUOTE FAILED")


def test_candles(symbol="AAPL"):

    print("\n🔥 TESTING CANDLE ENDPOINT")

    now = int(time.time())
    one_year = now - (365 * 24 * 60 * 60)

    data = request_debug(
        "stock/candle",
        {
            "symbol": symbol,
            "resolution": "D",
            "from": one_year,
            "to": now,
        }
    )

    if isinstance(data, dict):

        status = data.get("s")

        print("\nCANDLE STATUS:", status)

        if status == "ok":

            try:

                df = pd.DataFrame({
                    "Date": pd.to_datetime(data["t"], unit="s"),
                    "Open": data["o"],
                    "High": data["h"],
                    "Low": data["l"],
                    "Close": data["c"],
                    "Volume": data["v"],
                })

                print("\n✅ CANDLE SUCCESS")
                print(df.head())

            except Exception as e:
                print("❌ DATAFRAME BUILD FAILED:", e)

        else:
            print("❌ CANDLE RESPONSE INVALID")

    else:
        print("❌ CANDLE REQUEST FAILED")


def test_profile(symbol="AAPL"):

    print("\n🔥 TESTING PROFILE ENDPOINT")

    data = request_debug(
        "stock/profile2",
        {
            "symbol": symbol,
        }
    )

    if isinstance(data, dict):

        print("\n✅ PROFILE SUCCESS")

        print("Name:", data.get("name"))
        print("Ticker:", data.get("ticker"))
        print("Exchange:", data.get("exchange"))

    else:
        print("\n❌ PROFILE FAILED")


def test_bulk_quotes():

    print("\n🔥 TESTING BULK QUOTE LOAD")

    failures = 0
    successes = 0

    for i, symbol in enumerate(TEST_SYMBOLS):

        print("\n" + "-" * 60)
        print(f"{i+1}/{len(TEST_SYMBOLS)} {symbol}")

        try:

            data = request_debug(
                "quote",
                {
                    "symbol": symbol,
                }
            )

            if isinstance(data, dict) and data.get("c") is not None:
                successes += 1
            else:
                failures += 1

        except Exception:
            failures += 1

        time.sleep(0.5)

    print("\n" + "=" * 80)
    print("BULK TEST RESULTS")
    print("=" * 80)

    print("SUCCESS:", successes)
    print("FAILURES:", failures)


def test_rate_limit_behavior():

    print("\n🔥 TESTING RATE LIMIT BEHAVIOR")

    symbol = "AAPL"

    success = 0
    failure = 0

    for i in range(20):

        print(f"\nBURST REQUEST {i+1}/20")

        try:

            data = request_debug(
                "quote",
                {
                    "symbol": symbol,
                }
            )

            if isinstance(data, dict):
                success += 1
            else:
                failure += 1

        except Exception:
            failure += 1

        time.sleep(0.1)

    print("\n" + "=" * 80)
    print("RATE LIMIT TEST")
    print("=" * 80)

    print("SUCCESS:", success)
    print("FAILURE:", failure)


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 80)
    print("FINNHUB DEBUG TOOL")
    print("=" * 80)

    if not API_KEY:
        print("❌ NO API KEY FOUND")
        print("\nSet:")
        print("set FINNHUB_API_KEY=YOUR_KEY")
        return

    print("✅ API KEY FOUND")
    print("KEY PREFIX:", API_KEY[:8] + "...")

    # -----------------------------------------
    # BASIC TESTS
    # -----------------------------------------
    test_quote("AAPL")

    test_candles("AAPL")

    test_profile("AAPL")

    # -----------------------------------------
    # BULK TEST
    # -----------------------------------------
    test_bulk_quotes()

    # -----------------------------------------
    # RATE LIMIT TEST
    # -----------------------------------------
    test_rate_limit_behavior()

    print("\n" + "=" * 80)
    print("DONE")
    print("=" * 80)


if __name__ == "__main__":
    main()