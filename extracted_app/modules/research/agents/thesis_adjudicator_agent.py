"""Adjudicates bull/base/bear thesis from individual analyst findings."""
from __future__ import annotations
from typing import Any


def adjudicate_thesis(ticker: str, findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not findings:
        return {"ticker": ticker.upper(), "bull_case": [], "bear_case": [], "base_case": "Insufficient evidence.", "expected_return_score": 50}
    positives, risks = [], []
    score_sum = 0.0
    conf_sum = 0.0
    for f in findings:
        positives.extend(f.get("positives") or [])
        risks.extend(f.get("risks") or [])
        score_sum += float(f.get("score", 50) or 50) * float(f.get("confidence", 50) or 50)
        conf_sum += float(f.get("confidence", 50) or 50)
    expected = round(score_sum / conf_sum, 1) if conf_sum else 50.0
    return {
        "ticker": ticker.upper(),
        "bull_case": positives[:8],
        "bear_case": risks[:8],
        "base_case": f"The base case for {ticker.upper()} is {'constructive' if expected >= 60 else 'balanced' if expected >= 45 else 'cautious'} with a research score of {expected}/100.",
        "expected_return_score": expected,
    }
