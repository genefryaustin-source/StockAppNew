"""Investment council synthesis for bull/base/bear probability weighting."""
from __future__ import annotations
from typing import Any


def build_investment_council_view(ticker: str, committee: dict[str, Any], thesis: dict[str, Any]) -> dict[str, Any]:
    score = float(committee.get("score", 50) or 50)
    bull_prob = max(10, min(75, 20 + score * 0.65))
    bear_prob = max(10, min(65, 70 - score * 0.55))
    base_prob = max(10, 100 - bull_prob - bear_prob)
    # Normalize.
    total = bull_prob + bear_prob + base_prob
    bull_prob, base_prob, bear_prob = [round(x / total * 100, 1) for x in (bull_prob, base_prob, bear_prob)]
    expected_return = round((bull_prob * 0.22 + base_prob * 0.06 - bear_prob * 0.16), 1)
    expected_risk = round(100 - float(committee.get("confidence", 50) or 50) + float(committee.get("disagreement_score", 50) or 50) * 0.35, 1)
    return {
        "ticker": ticker.upper(),
        "bull_probability": bull_prob,
        "base_probability": base_prob,
        "bear_probability": bear_prob,
        "expected_return_score": expected_return,
        "expected_risk_score": max(0, min(100, expected_risk)),
        "recommendation": committee.get("rating", "Hold"),
        "bull_case": thesis.get("bull_case", []),
        "base_case": thesis.get("base_case", "Balanced base case."),
        "bear_case": thesis.get("bear_case", []),
    }
