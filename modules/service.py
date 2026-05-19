import requests
import pandas as pd
import yfinance as yf
import streamlit as st
import yaml
import os
import time
import random
from diskcache import Cache

# Load config
with open("config.yaml") as f:
    CONFIG = yaml.safe_load(f)["market_data"]

POLYGON_KEY = CONFIG.get("polygon_api_key")
FMP_KEY = CONFIG.get("fmp_api_key")
USE_YAHOO = CONFIG.get("enable_yahoo_fallback", True)

CACHE = Cache(CONFIG.get("cache_dir", "cache"))

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# Generic retry wrapper
def retry(func, retries=3):

    for attempt in range(retries):

        try:
            return func()

        except Exception:

            sleep = (2 ** attempt) + random.uniform(0.5, 1.5)
            time.sleep(sleep)

    raise Exception("All market data providers failed")

# Polygon provider
def polygon_price(symbol, period="1y", interval="1d"):

    if not POLYGON_KEY:
        raise Exception("Polygon key missing")

    multiplier = 1
    timespan = "day"

    if interval.endswith("m"):
        timespan = "minute"
        multiplier = int(interval.replace("m", ""))

    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/2020-01-01/2100-01-01"

    r = SESSION.get(url, params={"apiKey": POLYGON_KEY}, timeout=10)

    data = r.json()

    if "results" not in data:
        raise Exception("Polygon failed")

    df = pd.DataFrame(data["results"])

    df["Date"] = pd.to_datetime(df["t"], unit="ms")

    df.rename(columns={
        "o": "Open",
        "h": "High",
        "l": "Low",
        "c": "Close",
        "v": "Volume"
    }, inplace=True)

    return df

# FMP provider
def fmp_price(symbol):

    if not FMP_KEY:
        raise Exception("FMP key missing")

    url = f"https://financialmodelingprep.com/api/v3/historical-price-full/{symbol}"

    r = SESSION.get(url, params={"apikey": FMP_KEY})

    data = r.json()

    df = pd.DataFrame(data["historical"])

    df["Date"] = pd.to_datetime(df["date"])

    return df

# Yahoo fallback
def yahoo_price(symbol, period="1y", interval="1d"):

    ticker = yf.Ticker(symbol)

    df = ticker.history(period=period, interval=interval)

    df.reset_index(inplace=True)

    return df

# Unified enterprise function
@st.cache_data(ttl=900)
def get_price_history(symbol, period="1y", interval="1d"):

    cache_key = f"{symbol}_{period}_{interval}"

    if cache_key in CACHE:
        return CACHE[cache_key]

    providers = [
        lambda: polygon_price(symbol, period, interval),
        lambda: fmp_price(symbol),
    ]

    if USE_YAHOO:
        providers.append(lambda: yahoo_price(symbol, period, interval))

    for provider in providers:

        try:

            df = retry(provider)

            CACHE[cache_key] = df

            return df

        except Exception:

            continue

    raise Exception("All providers failed")

# Profile unified function
@st.cache_data(ttl=3600)
def get_company_profile(symbol):

    cache_key = f"profile_{symbol}"

    if cache_key in CACHE:
        return CACHE[cache_key]

    # Try Polygon
    try:

        url = f"https://api.polygon.io/v3/reference/tickers/{symbol}"

        r = SESSION.get(url, params={"apiKey": POLYGON_KEY})

        data = r.json()["results"]

        profile = {
            "name": data.get("name"),
            "sector": data.get("sic_description"),
            "market_cap": data.get("market_cap")
        }

        CACHE[cache_key] = profile

        return profile

    except Exception:
        pass

    # fallback Yahoo
    ticker = yf.Ticker(symbol)

    info = ticker.get_info()

    CACHE[cache_key] = info

    return info