from __future__ import annotations
from typing import Any
from .research_utils import _stable_score


def build_analyst_consensus(ticker: str) -> dict[str, Any]:
    score = _stable_score(ticker, 21, 56, 24)
    dispersion = _stable_score(ticker, 22, 35, 20)
    revision = _stable_score(ticker, 23, 52, 28)
    label = "Bullish" if score >= 65 else "Neutral" if score >= 40 else "Bearish"
    return {
        "ticker": ticker.upper(),
        "analyst_score": score,
        "consensus": label,
        "price_target_bias": "Upside" if score >= 55 else "Limited Upside",
        "analyst_dispersion": dispersion,
        "revision_momentum": revision,
        "upgrades_30d": int(max(0, round((revision - 45) / 12))),
        "downgrades_30d": int(max(0, round((45 - revision) / 12))),
        "notes": [
            "Consensus support is favorable" if score >= 60 else "Consensus is mixed",
            "Revision momentum is improving" if revision >= 55 else "Revision momentum is not yet confirmed",
            "Analyst dispersion is elevated" if dispersion >= 55 else "Analyst dispersion is manageable",
        ],
    }
