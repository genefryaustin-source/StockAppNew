"""
modules/risk_layer/scanner_bridge.py

Runs the AI Scanner's own condition evaluator (modules.alerts.scanner_engine)
against every held position with a small set of built-in risk-oriented
presets (overbought/oversold, below-200-SMA, shock-day moves, high risk
score) -- no LLM call needed since these are fixed thresholds, not
natural-language rules. This is the same evaluate_condition() function the
AI Scanner page uses per-rule, just pointed at the portfolio's own symbols
instead of a saved alert rule.

Forex pairs are handled separately: evaluate_condition() always pulls
price history through modules.market_data.service, which is an
equity-oriented provider chain (Polygon/MarketData/Alpha Vantage's stock
endpoints) that has no way to resolve a symbol like "EUR/USD" -- it was
just quietly returning empty and burning through the whole failover chain
every time. Forex symbols get their own lightweight preset check here,
computed from real history pulled via the Forex module's own provider
router (modules.forex.providers.forex_provider_router), the same one the
Forex page itself uses.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from modules.alerts.scanner_engine import ScanCondition, evaluate_condition
from modules.risk_layer.classification import classify_asset_class

RISK_PRESETS: dict[str, ScanCondition] = {
    "Overbought (RSI > 70)": ScanCondition(rsi_above=70),
    "Oversold (RSI < 30)": ScanCondition(rsi_below=30),
    "Below 200-day trend": ScanCondition(price_below_sma=200),
    "Sharp single-day drop (< -5%)": ScanCondition(day_change_pct_below=-5.0),
    "Elevated risk score": ScanCondition(risk_above=70),
}


def _forex_closes(pair: str, lookback_days: int = 400) -> pd.Series | None:
    """Pulls daily closes for a forex pair via the Forex module's own
    provider router -- never the equity get_price_history path."""
    try:
        from modules.forex.providers.forex_provider_router import get_forex_daily_history_from_router
    except Exception:
        return None

    end = date.today()
    start = end - timedelta(days=lookback_days)
    try:
        payload = get_forex_daily_history_from_router(pair, start_date=start, end_date=end)
    except Exception:
        return None

    rows = payload.get("rows") or []
    if not rows:
        return None
    df = pd.DataFrame(rows)
    if "asof" not in df.columns or "close" not in df.columns:
        return None
    return df.sort_values("asof").set_index("asof")["close"].dropna()


def _scan_forex_symbol(pair: str) -> list[dict]:
    """Overbought/oversold/trend/shock-move checks for a forex pair, using
    the same preset thresholds as RISK_PRESETS but computed locally against
    real FX history rather than via the equity-oriented evaluate_condition."""
    closes = _forex_closes(pair)
    if closes is None or len(closes) < 30:
        return []

    flags = []
    delta = closes.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = (100 - 100 / (1 + rs)).iloc[-1]

    if pd.notna(rsi):
        if rsi > 70:
            flags.append({"preset": "Overbought (RSI > 70)", "reason": f"RSI={rsi:.1f}"})
        elif rsi < 30:
            flags.append({"preset": "Oversold (RSI < 30)", "reason": f"RSI={rsi:.1f}"})

    if len(closes) >= 200:
        sma200 = closes.rolling(200).mean().iloc[-1]
        last = closes.iloc[-1]
        if pd.notna(sma200) and last < sma200:
            flags.append({"preset": "Below 200-day trend",
                          "reason": f"price {last:.4f} below 200-day average {sma200:.4f}"})

    day_chg = closes.pct_change().iloc[-1] * 100
    if pd.notna(day_chg) and day_chg < -5.0:
        flags.append({"preset": "Sharp single-day drop (< -5%)", "reason": f"{day_chg:+.2f}% day change"})

    return flags


def scan_positions(db, symbols: list[str]) -> dict:
    """
    Returns {symbol: [{"preset": name, "reason": str}, ...]} for every
    symbol that trips at least one preset. Symbols that error out (e.g. no
    price history) are silently skipped, not raised -- this is a risk
    overlay, not a blocking dependency.
    """
    flags: dict[str, list] = {}
    for symbol in dict.fromkeys(symbols):  # de-dupe, preserve order
        asset_class = classify_asset_class(symbol)

        if asset_class == "forex":
            try:
                fx_flags = _scan_forex_symbol(symbol)
            except Exception:
                fx_flags = []
            if fx_flags:
                flags[symbol] = fx_flags
            continue

        if asset_class == "crypto":
            # Same underlying problem as forex used to have -- evaluate_condition()
            # resolves price history through the equity provider chain, which
            # doesn't know crypto tickers either. Skipping rather than burning
            # through a guaranteed-empty failover chain. A dedicated crypto
            # scanner (via modules.crypto.data_service) is a reasonable follow-up,
            # not yet built.
            continue

        for name, condition in RISK_PRESETS.items():
            try:
                fired, reason = evaluate_condition(symbol, condition, db)
            except Exception:
                continue
            if fired:
                flags.setdefault(symbol, []).append({"preset": name, "reason": reason})
    return flags
