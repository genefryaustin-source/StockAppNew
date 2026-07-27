"""Capital allocation and portfolio heat engine for Phase 11."""
from __future__ import annotations
from typing import Any


def _num(v: Any, d: float = 0.0) -> float:
    try: return float(v if v is not None else d)
    except Exception: return d


def calculate_allocation_plan(state: dict[str, Any]) -> dict[str, Any]:
    budget = max(1.0, _num(state.get("risk_budget"), 100000.0))
    exposure = abs(_num(state.get("total_market_value")))
    heat = min(100.0, exposure / budget * 100.0)
    cash = max(0.0, budget - exposure)
    delta = _num(state.get("net_delta"))
    vega = _num(state.get("net_vega"))
    theta = _num(state.get("net_theta"))
    target = {
        "max_single_trade_pct": 3.0,
        "max_strategy_bucket_pct": 15.0,
        "max_total_options_heat_pct": 35.0,
        "target_delta_band": "-0.25 to +0.35",
        "target_vega_band": "balanced unless volatility edge exists",
    }
    actions = []
    if heat > target["max_total_options_heat_pct"]:
        actions.append("Reduce gross options exposure before adding new trades.")
    if abs(delta) > 1.0:
        actions.append("Rebalance delta exposure with hedges or offsetting spreads.")
    if vega > 1.0:
        actions.append("Portfolio is long-volatility biased; consider short-vega income trades only if regime supports it.")
    if theta < -1.0:
        actions.append("Theta bleed is elevated; review long premium positions.")
    if not actions:
        actions.append("Allocation within default guardrails. New trades may be sized normally.")
    return {"capital_heat_pct": round(heat, 1), "available_risk_budget": round(cash, 2), "target_policy": target, "allocation_actions": actions}
