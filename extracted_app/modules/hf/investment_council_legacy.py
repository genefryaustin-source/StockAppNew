"""
modules/hf/investment_council_v2.py

Scenario-based investment council layer for HF-2 multi-agent research.
"""
from __future__ import annotations
from typing import Any


def build_investment_council_view(report: dict[str, Any]) -> dict[str, Any]:
    consensus = dict(report.get("consensus") or {})
    score = float(consensus.get("score", 50.0) or 50.0)
    confidence = float(consensus.get("confidence", 50.0) or 50.0)

    bull_return = round(max(5.0, (score - 50) * 0.9 + confidence * 0.15), 1)
    base_return = round((score - 50) * 0.35, 1)
    bear_return = round(-max(5.0, (60 - score) * 0.6 + (100 - confidence) * 0.12), 1)

    bull_prob = min(55.0, max(20.0, score * 0.45))
    bear_prob = min(45.0, max(15.0, (100 - score) * 0.35))
    base_prob = max(10.0, 100.0 - bull_prob - bear_prob)
    total = bull_prob + base_prob + bear_prob
    bull_prob, base_prob, bear_prob = bull_prob / total, base_prob / total, bear_prob / total

    expected_return = round(bull_return * bull_prob + base_return * base_prob + bear_return * bear_prob, 1)
    return {
        "bull_case": {"probability": round(bull_prob, 2), "return_pct": bull_return},
        "base_case": {"probability": round(base_prob, 2), "return_pct": base_return},
        "bear_case": {"probability": round(bear_prob, 2), "return_pct": bear_return},
        "expected_return_pct": expected_return,
        "risk_reward": round(abs(expected_return / bear_return), 2) if bear_return else None,
        "council_action": _action(expected_return, confidence),
    }


def _action(expected_return: float, confidence: float) -> str:
    if expected_return >= 12 and confidence >= 60:
        return "Candidate for Core Long Review"
    if expected_return >= 6:
        return "Candidate for Starter Position / Watchlist"
    if expected_return <= -5:
        return "Avoid / Short Watch"
    return "Monitor"
