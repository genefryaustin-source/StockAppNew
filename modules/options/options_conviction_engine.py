"""
modules/options/options_conviction_engine.py

Phase 3 — Institutional conviction scoring engine.
"""
from __future__ import annotations

from typing import Any


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or default)
    except Exception:
        return default


def score_copilot_conviction(smart_report: dict[str, Any], dealer_report: dict[str, Any] | None, positioning: dict[str, Any]) -> dict[str, Any]:
    dealer_report = dealer_report or {}
    score = 0.0
    reasons: list[str] = []

    smart_conviction = _num((smart_report.get("conviction_score") or {}).get("score"))
    sentiment_score = _num((smart_report.get("sentiment") or {}).get("score"), 50)
    whale_count = _num((smart_report.get("whale_summary") or {}).get("whale_count"))
    sweep_count = _num((smart_report.get("sweep_summary") or {}).get("sweep_count"))
    concentration = _num(positioning.get("premium_concentration"))

    score += min(30, smart_conviction * 0.30)
    score += min(20, abs(sentiment_score - 50) * 0.55)
    score += min(20, whale_count * 4)
    score += min(15, sweep_count * 2)
    score += min(15, concentration * 45)

    if smart_conviction >= 70:
        reasons.append("Smart Money conviction is high.")
    if whale_count:
        reasons.append(f"Detected {int(whale_count)} whale/block candidates.")
    if sweep_count:
        reasons.append(f"Detected {int(sweep_count)} aggressive sweep candidates.")
    if concentration >= 0.30:
        reasons.append("Premium is concentrated around a clear strike/expiry magnet.")

    if dealer_report:
        dealer_summary = dealer_report.get("dealer_summary") or dealer_report
        if dealer_summary.get("net_gex") is not None:
            score += 5
            reasons.append("Dealer exposure context is available.")

    score = round(max(0, min(100, score)), 1)
    if score >= 80:
        label = "Extreme"
    elif score >= 65:
        label = "Strong"
    elif score >= 45:
        label = "Moderate"
    else:
        label = "Low"

    return {"score": score, "label": label, "reasons": reasons or ["No dominant institutional signal detected."]}
