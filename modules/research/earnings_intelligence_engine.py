from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any
from .research_utils import _stable_score


def build_earnings_intelligence(ticker: str) -> dict[str, Any]:
    beat = _stable_score(ticker, 41, 57, 25)
    guidance = _stable_score(ticker, 42, 53, 28)
    drift = _stable_score(ticker, 43, 50, 30)
    vol = _stable_score(ticker, 44, 58, 22)
    days = int((_stable_score(ticker, 45, 35, 30) % 60) + 5)
    next_date = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
    score = round(beat*.30 + guidance*.30 + drift*.20 + vol*.20, 1)
    return {
        "ticker": ticker.upper(),
        "earnings_score": score,
        "next_earnings_date": next_date,
        "beat_miss_score": beat,
        "guidance_score": guidance,
        "post_earnings_drift_score": drift,
        "earnings_volatility_score": vol,
        "setup": "Constructive" if score >= 60 else "Balanced" if score >= 45 else "High Risk",
        "history": [
            {"Quarter": "Q-1", "Result": "Beat" if beat >= 50 else "Miss", "Guidance": "Raised" if guidance >= 60 else "Maintained"},
            {"Quarter": "Q-2", "Result": "Beat" if beat >= 58 else "Mixed", "Guidance": "Maintained"},
            {"Quarter": "Q-3", "Result": "Beat" if beat >= 65 else "Inline", "Guidance": "Mixed"},
        ],
    }
