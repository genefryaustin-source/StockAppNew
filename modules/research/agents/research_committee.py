"""Research committee vote aggregation."""
from __future__ import annotations
from collections import Counter
from typing import Any


def committee_vote(findings: list[dict[str, Any]]) -> dict[str, Any]:
    if not findings:
        return {"rating": "Hold", "score": 50, "confidence": 0, "votes": {}, "agreement_score": 0, "disagreement_score": 100}
    votes = Counter(str(f.get("rating", "Hold")) for f in findings)
    weighted = 0.0
    weights = 0.0
    for f in findings:
        conf = float(f.get("confidence", 50) or 50)
        weighted += float(f.get("score", 50) or 50) * conf
        weights += conf
    score = round(weighted / weights, 1) if weights else 50.0
    if score >= 85: rating = "Strong Buy"
    elif score >= 68: rating = "Buy"
    elif score >= 54: rating = "Hold"
    elif score >= 40: rating = "Reduce"
    elif score >= 25: rating = "Sell"
    else: rating = "Strong Sell"
    top_vote_count = max(votes.values()) if votes else 0
    agreement = round(top_vote_count / max(1, len(findings)) * 100, 1)
    return {
        "rating": rating,
        "score": score,
        "confidence": round(sum(float(f.get("confidence", 50) or 50) for f in findings) / len(findings), 1),
        "votes": dict(votes),
        "agreement_score": agreement,
        "disagreement_score": round(100 - agreement, 1),
    }
