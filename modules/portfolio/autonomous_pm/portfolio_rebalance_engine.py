"""Autonomous rebalance recommendation engine."""
from __future__ import annotations
from typing import Any


def _num(v: Any, d: float = 0.0) -> float:
    try: return float(v if v is not None else d)
    except Exception: return d


def build_rebalance_plan(state: dict[str, Any], allocation: dict[str, Any]) -> dict[str, Any]:
    recommendations = []
    if allocation.get("capital_heat_pct", 0) > 35:
        recommendations.append({"priority": "High", "action": "Reduce position heat", "rationale": "Options exposure exceeds target heat."})
    if _num(state.get("net_delta")) > 1.0:
        recommendations.append({"priority": "Medium", "action": "Add downside hedge", "rationale": "Portfolio is delta-heavy bullish."})
    elif _num(state.get("net_delta")) < -1.0:
        recommendations.append({"priority": "Medium", "action": "Add upside hedge or close bearish exposure", "rationale": "Portfolio is delta-heavy bearish."})
    if _num(state.get("net_theta")) < -1.0:
        recommendations.append({"priority": "Medium", "action": "Convert long premium to defined-risk spreads", "rationale": "Theta drag is elevated."})
    if not recommendations:
        recommendations.append({"priority": "Normal", "action": "No rebalance required", "rationale": "Portfolio is inside default autonomous PM bands."})
    return {"rebalance_required": any(r["priority"] in {"High", "Medium"} for r in recommendations), "recommendations": recommendations}
