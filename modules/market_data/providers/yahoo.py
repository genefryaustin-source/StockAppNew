import pandas as pd
import yfinance as yf
import requests

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent":"Mozilla/5.0"})

def fetch_ohlcv(symbol: str, period: str, interval: str, timeout: int):
    t = yf.Ticker(symbol, session=_SESSION)
    df = t.history(period=period, interval=interval)
    if df is None or df.empty:
        raise RuntimeError("Yahoo returned empty data")
    df = df.reset_index()
    # yfinance uses "Date" or "Datetime"
    if "Datetime" in df.columns and "Date" not in df.columns:
        df.rename(columns={"Datetime":"Date"}, inplace=True)
    keep = ["Date","Open","High","Low","Close","Volume"]
    return df[keep]