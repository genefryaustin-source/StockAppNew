"""
Sprint 4 Phase 2 — Institutional Flow Confidence Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd


def score_flow_confidence(classification: dict[str, Any]) -> dict[str, Any]:
    if not classification or not classification.get("available"):
        return {"available": False, "reason": (classification or {}).get("reason", "No classification available."), "confidence_score": 0, "confidence_grade": "UNAVAILABLE"}

    df = classification.get("classified")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No classified rows.", "confidence_score": 0, "confidence_grade": "UNAVAILABLE"}

    total_premium = float(df.get("premium", pd.Series(dtype=float)).sum() or 0)
    total_volume = float(df.get("volume", pd.Series(dtype=float)).sum() or 0)
    high_voi = float((df.get("vol_oi_ratio", pd.Series(dtype=float)).fillna(0) >= 2).mean()) if len(df) else 0
    price_quality = float((df.get("near_ask", False) | df.get("near_bid", False)).mean()) if len(df) else 0

    summary = classification.get("summary")
    concentration = 0.0
    if isinstance(summary, pd.DataFrame) and not summary.empty and total_premium > 0:
        concentration = float(summary.iloc[0]["premium"] / max(1.0, total_premium))

    premium_score = min(1.0, total_premium / 2_000_000)
    volume_score = min(1.0, total_volume / 10_000)

    score = round(
        premium_score * 30
        + volume_score * 20
        + high_voi * 20
        + price_quality * 15
        + concentration * 15,
        2,
    )

    if score >= 80:
        grade = "VERY_HIGH"
    elif score >= 65:
        grade = "HIGH"
    elif score >= 45:
        grade = "MEDIUM"
    elif score >= 25:
        grade = "LOW"
    else:
        grade = "NOISY"

    return {
        "available": True,
        "confidence_score": score,
        "confidence_grade": grade,
        "premium_score": round(premium_score, 3),
        "volume_score": round(volume_score, 3),
        "high_voi_share": round(high_voi, 3),
        "price_quality_share": round(price_quality, 3),
        "dominant_concentration": round(concentration, 3),
    }


def summarize_flow_confidence(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Flow confidence unavailable: {result.get('reason', 'unknown reason')}"
    return f"Flow confidence is {result.get('confidence_grade')} with score {result.get('confidence_score')}/100."
