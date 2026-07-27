"""
Sprint 4 Phase 2 — Flow Accumulation Engine.
"""
from __future__ import annotations

from typing import Any
import pandas as pd

BULLISH_CLASSES = {"BULLISH_SPECULATION", "PUT_DISTRIBUTION", "OPENING_FLOW"}
BEARISH_CLASSES = {"BEARISH_SPECULATION", "CALL_DISTRIBUTION", "PROTECTIVE_HEDGING"}


def detect_accumulation(classification: dict[str, Any]) -> dict[str, Any]:
    if not classification or not classification.get("available"):
        return {"available": False, "reason": (classification or {}).get("reason", "No classification available.")}

    df = classification.get("classified")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {"available": False, "reason": "No classified rows."}

    df = df.copy()
    df["premium"] = pd.to_numeric(df.get("premium", 0), errors="coerce").fillna(0)
    df["volume"] = pd.to_numeric(df.get("volume", 0), errors="coerce").fillna(0)
    df["flow_class"] = df.get("flow_class", "").astype(str)

    bullish = df[df["flow_class"].isin(BULLISH_CLASSES)]
    bearish = df[df["flow_class"].isin(BEARISH_CLASSES)]

    bull_premium = float(bullish["premium"].sum())
    bear_premium = float(bearish["premium"].sum())
    total = max(1.0, bull_premium + bear_premium)
    accumulation_score = round(50 + ((bull_premium - bear_premium) / total) * 50, 2)

    if accumulation_score >= 65:
        regime = "ACCUMULATION"
        bias = "BULLISH"
    elif accumulation_score <= 35:
        regime = "DISTRIBUTION"
        bias = "BEARISH"
    else:
        regime = "BALANCED"
        bias = "NEUTRAL"

    return {
        "available": True,
        "accumulation_score": accumulation_score,
        "regime": regime,
        "bias": bias,
        "bullish_premium": round(bull_premium, 2),
        "bearish_premium": round(bear_premium, 2),
        "bullish_share": round(bull_premium / total, 3),
        "bearish_share": round(bear_premium / total, 3),
    }


def summarize_accumulation(result: dict[str, Any]) -> str:
    if not result.get("available"):
        return f"Accumulation unavailable: {result.get('reason', 'unknown reason')}"
    return f"Flow regime is {result.get('regime')} / {result.get('bias')} with score {result.get('accumulation_score')}/100."
