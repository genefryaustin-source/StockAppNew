from __future__ import annotations

import pandas as pd

from modules.options.providers.common import build_chain_payload, calc_dte, safe_float


def get_expirations(ticker: str) -> list[str]:
    try:
        import yfinance as yf  # type: ignore
        tk = yf.Ticker(ticker.upper())
        return sorted([str(x)[:10] for x in (tk.options or []) if x])
    except Exception:
        return []


def _normalize_df(
    df: pd.DataFrame,
    ticker: str,
    expiry: str,
    opt_type: str,
    underlying_price: float | None = None,
) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["option_symbol"] = df.get("contractSymbol", "")
    out["expiry"] = expiry
    out["expiration"] = expiry
    out["strike"] = pd.to_numeric(df.get("strike"), errors="coerce")
    out["type"] = opt_type
    out["side"] = opt_type
    out["bid"] = pd.to_numeric(df.get("bid"), errors="coerce")
    out["ask"] = pd.to_numeric(df.get("ask"), errors="coerce")
    out["mid"] = ((out["bid"].fillna(0) + out["ask"].fillna(0)) / 2.0).where((out["bid"].fillna(0) + out["ask"].fillna(0)) > 0, pd.NA)
    out["last"] = pd.to_numeric(df.get("lastPrice"), errors="coerce")
    out["volume"] = pd.to_numeric(df.get("volume"), errors="coerce").fillna(0)
    out["open_interest"] = pd.to_numeric(df.get("openInterest"), errors="coerce").fillna(0)
    out["iv"] = pd.to_numeric(df.get("impliedVolatility"), errors="coerce")
    out["delta"] = None
    out["gamma"] = None
    out["theta"] = None
    out["vega"] = None
    dte = calc_dte(expiry)

    if dte is None or dte <= 0:
        dte = 1

    out["dte"] = dte
    out["underlying"] = ticker.upper()

    out["underlying_price"] = pd.to_numeric(
        underlying_price,
        errors="coerce",
    )

    return out


def get_chain(ticker: str, expiration: str | None = None) -> dict:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return build_chain_payload(ticker, pd.DataFrame(), "yahoo", "yfinance is not installed")

    try:
        tk = yf.Ticker(ticker.upper())

        underlying_price = None

        try:
            fi = getattr(tk, "fast_info", None)

            if fi:
                underlying_price = (
                        fi.get("lastPrice")
                        or fi.get("regularMarketPrice")
                        or fi.get("previousClose")
                )
        except Exception:
            pass

        if underlying_price is None:
            try:
                info = tk.info or {}
                underlying_price = (
                        info.get("regularMarketPrice")
                        or info.get("currentPrice")
                        or info.get("previousClose")
                )
            except Exception:
                pass
        expirations = [expiration] if expiration else sorted([str(x)[:10] for x in (tk.options or []) if x])
        if not expirations:
            return build_chain_payload(ticker, pd.DataFrame(), "yahoo", f"Yahoo returned no expirations for {ticker}")
        exp = expirations[0]
        chain = tk.option_chain(exp)
        calls = _normalize_df(
            chain.calls,
            ticker,
            exp,
            "call",
            underlying_price,
        )

        puts = _normalize_df(
            chain.puts,
            ticker,
            exp,
            "put",
            underlying_price,
        )
        df = pd.concat([calls, puts], ignore_index=True) if not calls.empty or not puts.empty else pd.DataFrame()
        return build_chain_payload(ticker, df, "yahoo")
    except Exception as e:
        return build_chain_payload(ticker, pd.DataFrame(), "yahoo", f"Yahoo options error: {e}")
