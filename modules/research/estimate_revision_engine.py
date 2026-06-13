from __future__ import annotations
from typing import Any
from .research_utils import _stable_score


def build_estimate_revisions(ticker: str) -> dict[str, Any]:
    eps = _stable_score(ticker, 31, 55, 30)
    revenue = _stable_score(ticker, 32, 54, 26)
    ebitda = _stable_score(ticker, 33, 52, 24)
    composite = round(eps*.45 + revenue*.35 + ebitda*.20, 1)
    return {
        "ticker": ticker.upper(),
        "revision_score": composite,
        "eps_revision_score": eps,
        "revenue_revision_score": revenue,
        "ebitda_revision_score": ebitda,
        "direction": "Positive" if composite >= 60 else "Neutral" if composite >= 42 else "Negative",
        "table": [
            {"Estimate": "EPS", "Momentum": eps, "Read": "Upward" if eps >= 55 else "Flat/Down"},
            {"Estimate": "Revenue", "Momentum": revenue, "Read": "Upward" if revenue >= 55 else "Flat/Down"},
            {"Estimate": "EBITDA", "Momentum": ebitda, "Read": "Upward" if ebitda >= 55 else "Flat/Down"},
        ],
    }
