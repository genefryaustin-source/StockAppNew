from __future__ import annotations
from typing import Any
from .research_utils import _stable_score


def build_institutional_ownership(ticker: str) -> dict[str, Any]:
    accumulation = _stable_score(ticker, 51, 54, 30)
    conviction = _stable_score(ticker, 52, 55, 26)
    activity = _stable_score(ticker, 53, 50, 30)
    score = round(accumulation*.45 + conviction*.35 + activity*.20, 1)
    return {
        "ticker": ticker.upper(),
        "institutional_score": score,
        "accumulation_score": accumulation,
        "fund_conviction_score": conviction,
        "activity_score": activity,
        "ownership_read": "Accumulation" if score >= 60 else "Neutral" if score >= 42 else "Distribution",
        "activity": [
            {"Type": "New Positions", "Score": max(0, round(accumulation - 10, 1))},
            {"Type": "Added Positions", "Score": accumulation},
            {"Type": "Reduced Positions", "Score": max(0, round(100 - accumulation, 1))},
            {"Type": "Closed Positions", "Score": max(0, round(80 - conviction, 1))},
        ],
    }
