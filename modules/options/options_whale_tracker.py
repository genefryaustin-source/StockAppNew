"""
modules/options/options_whale_tracker.py

Classifies unusual options contracts into whale/block/standard activity.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def classify_whale(row: dict[str, Any]) -> str:
    premium = _num(row.get("premium_est"))
    volume = _num(row.get("volume"))
    vol_oi = _num(row.get("vol_oi_ratio"))

    if premium >= 5_000_000 or (premium >= 2_000_000 and vol_oi >= 5):
        return "Mega Whale"
    if premium >= 1_000_000:
        return "Whale"
    if premium >= 250_000 or volume >= 2_500:
        return "Institutional Block"
    if premium >= 100_000 or vol_oi >= 5:
        return "Large Trader"
    return "Standard"


def whale_score(row: dict[str, Any]) -> float:
    premium = _num(row.get("premium_est"))
    volume = _num(row.get("volume"))
    vol_oi = _num(row.get("vol_oi_ratio"))
    iv_pct = _num(row.get("iv_pct"))

    score = 0.0
    score += min(45, premium / 5_000_000 * 45)
    score += min(25, volume / 5_000 * 25)
    score += min(20, vol_oi / 10 * 20)
    score += min(10, iv_pct / 150 * 10)
    return round(max(0.0, min(100.0, score)), 1)


def track_whales(unusual_contracts: list[dict[str, Any]], limit: int = 25) -> list[dict[str, Any]]:
    whales: list[dict[str, Any]] = []
    for item in unusual_contracts or []:
        row = dict(item)
        row["whale_class"] = classify_whale(row)
        row["whale_score"] = whale_score(row)
        row["direction"] = "Bullish" if str(row.get("type", "")).upper() == "CALL" else "Bearish" if str(row.get("type", "")).upper() == "PUT" else "Neutral"
        row["conviction_flag"] = row["whale_class"] in {"Mega Whale", "Whale", "Institutional Block"}
        whales.append(row)
    whales.sort(key=lambda r: (_num(r.get("whale_score")), _num(r.get("premium_est"))), reverse=True)
    return whales[:limit]


def whales_frame(whales: list[dict[str, Any]]) -> pd.DataFrame:
    if not whales:
        return pd.DataFrame()
    df = pd.DataFrame(whales)
    preferred = [
        "ticker", "type", "expiry", "strike", "whale_class", "whale_score",
        "premium_fmt", "premium_est", "volume", "open_interest", "vol_oi_ratio",
        "iv_pct", "otm_pct", "direction", "sentiment",
    ]
    cols = [c for c in preferred if c in df.columns]
    return df[cols].copy()


def whale_summary(whales: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(whales or [])
    premium = sum(_num(w.get("premium_est")) for w in whales or [])
    calls = [w for w in whales or [] if str(w.get("type", "")).upper() == "CALL"]
    puts = [w for w in whales or [] if str(w.get("type", "")).upper() == "PUT"]
    mega = [w for w in whales or [] if w.get("whale_class") == "Mega Whale"]
    conviction = sum(1 for w in whales or [] if w.get("conviction_flag"))
    return {
        "whale_count": total,
        "mega_whale_count": len(mega),
        "conviction_count": conviction,
        "call_whales": len(calls),
        "put_whales": len(puts),
        "whale_premium": premium,
        "bullish_whale_pct": len(calls) / total if total else 0,
        "bearish_whale_pct": len(puts) / total if total else 0,
    }
