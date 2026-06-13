"""Strategy optimizer for Phase 5."""
from __future__ import annotations
from typing import Any


def _n(v: Any, d: float = 0.0) -> float:
    try:
        return float(v or d)
    except Exception:
        return d


def optimize_strategy_candidates(candidates: list[dict[str, Any]], objective: str = "Best Overall") -> dict[str, Any]:
    if not candidates:
        return {"error": "No candidates available"}
    objective = objective.lower()
    if "probability" in objective:
        key = lambda c: _n((c.get("score") or {}).get("probability_score"))
    elif "roi" in objective:
        key = lambda c: _n((c.get("metrics") or {}).get("expected_value")) / max(1.0, _n((c.get("metrics") or {}).get("capital_required"), 1.0))
    elif "income" in objective or "theta" in objective:
        key = lambda c: _n((c.get("score") or {}).get("theta_score"))
    elif "volatility" in objective or "vega" in objective:
        key = lambda c: _n((c.get("score") or {}).get("vega_score"))
    elif "smart" in objective:
        key = lambda c: _n((c.get("score") or {}).get("smart_money_alignment_score"))
    elif "dealer" in objective:
        key = lambda c: _n((c.get("score") or {}).get("dealer_alignment_score"))
    elif "safe" in objective or "risk" in objective:
        key = lambda c: _n((c.get("score") or {}).get("probability_score")) + _n((c.get("score") or {}).get("gamma_score"))
    else:
        key = lambda c: _n(c.get("overall_score"))
    best = max(candidates, key=key)
    return {
        "objective": objective.title(),
        "best_strategy": best,
        "top_5": sorted(candidates, key=key, reverse=True)[:5],
    }


def scenario_objectives() -> list[str]:
    return [
        "Best Overall",
        "Highest Probability",
        "Highest ROI",
        "Safest Risk-Controlled",
        "Best Income / Theta",
        "Best Volatility / Vega",
        "Best Smart Money Alignment",
        "Best Dealer Alignment",
    ]
