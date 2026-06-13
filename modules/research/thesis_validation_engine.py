from __future__ import annotations
from typing import Any


def validate_thesis(ticker: str, thesis: dict[str, Any], scorecard: dict[str, Any]) -> dict[str, Any]:
    score = float(scorecard.get("composite_research_score", 50) or 50)
    checks = [
        {"Check": "Fundamental support", "Pass": scorecard.get("fundamental_score", 50) >= 50},
        {"Check": "Analyst/revision confirmation", "Pass": (scorecard.get("analyst_score", 50) + scorecard.get("revision_score", 50)) / 2 >= 50},
        {"Check": "Institutional confirmation", "Pass": scorecard.get("institutional_score", 50) >= 50},
        {"Check": "Macro/sector alignment", "Pass": (scorecard.get("macro_score", 50) + scorecard.get("sector_score", 50)) / 2 >= 45},
    ]
    confidence = round(sum(1 for c in checks if c["Pass"]) / len(checks) * 100, 1)
    return {"ticker": ticker.upper(), "validated": confidence >= 50, "confidence": confidence, "checks": checks,
            "decision": "Proceed with defined-risk expression" if confidence >= 75 else "Proceed carefully" if confidence >= 50 else "Do not express until thesis improves"}
