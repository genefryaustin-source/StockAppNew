"""
modules/options/options_sweep_detector.py

Rule-based sweep/aggressive-flow detector using existing unusual-contract data.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def classify_sweep(row: dict[str, Any]) -> str:
    vol = _num(row.get("volume"))
    oi = _num(row.get("open_interest"))
    vol_oi = _num(row.get("vol_oi_ratio"))
    premium = _num(row.get("premium_est"))
    opt_type = str(row.get("type", "")).upper()

    aggressive = vol_oi >= 5 and vol >= 500 and premium >= 100_000
    extreme = vol_oi >= 10 and premium >= 500_000
    opening = vol > oi * 1.25 if oi > 0 else False

    if extreme:
        base = "Extreme Sweep"
    elif aggressive:
        base = "Sweep Candidate"
    elif opening and premium >= 100_000:
        base = "Opening Flow"
    elif premium >= 250_000:
        base = "Large Premium Print"
    else:
        base = "Unusual Activity"

    if opt_type == "CALL":
        return f"{base} — Calls"
    if opt_type == "PUT":
        return f"{base} — Puts"
    return base


def sweep_score(row: dict[str, Any]) -> float:
    vol = _num(row.get("volume"))
    vol_oi = _num(row.get("vol_oi_ratio"))
    premium = _num(row.get("premium_est"))
    score = 0.0
    score += min(35, vol_oi / 12 * 35)
    score += min(30, premium / 2_000_000 * 30)
    score += min(25, vol / 5_000 * 25)
    if vol_oi >= 5 and premium >= 100_000:
        score += 10
    return round(max(0, min(100, score)), 1)


def detect_sweeps(unusual_contracts: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    sweeps: list[dict[str, Any]] = []
    for item in unusual_contracts or []:
        row = dict(item)
        row["sweep_type"] = classify_sweep(row)
        row["sweep_score"] = sweep_score(row)
        row["opening_flow"] = _num(row.get("volume")) > _num(row.get("open_interest")) * 1.25 if _num(row.get("open_interest")) > 0 else False
        row["aggressive"] = row["sweep_score"] >= 60
        row["direction"] = "Bullish" if str(row.get("type", "")).upper() == "CALL" else "Bearish" if str(row.get("type", "")).upper() == "PUT" else "Neutral"
        if row["sweep_score"] >= 35:
            sweeps.append(row)
    sweeps.sort(key=lambda r: (_num(r.get("sweep_score")), _num(r.get("premium_est"))), reverse=True)
    return sweeps[:limit]


def sweeps_frame(sweeps: list[dict[str, Any]]) -> pd.DataFrame:
    if not sweeps:
        return pd.DataFrame()
    df = pd.DataFrame(sweeps)
    preferred = [
        "ticker", "type", "expiry", "strike", "sweep_type", "sweep_score",
        "premium_fmt", "premium_est", "volume", "open_interest", "vol_oi_ratio",
        "opening_flow", "aggressive", "direction",
    ]
    return df[[c for c in preferred if c in df.columns]].copy()


def sweep_summary(sweeps: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(sweeps or [])
    aggressive = sum(1 for s in sweeps or [] if s.get("aggressive"))
    opening = sum(1 for s in sweeps or [] if s.get("opening_flow"))
    call_sweeps = [s for s in sweeps or [] if str(s.get("type", "")).upper() == "CALL"]
    put_sweeps = [s for s in sweeps or [] if str(s.get("type", "")).upper() == "PUT"]
    return {
        "sweep_count": total,
        "aggressive_count": aggressive,
        "opening_flow_count": opening,
        "call_sweeps": len(call_sweeps),
        "put_sweeps": len(put_sweeps),
        "sweep_premium": sum(_num(s.get("premium_est")) for s in sweeps or []),
    }
