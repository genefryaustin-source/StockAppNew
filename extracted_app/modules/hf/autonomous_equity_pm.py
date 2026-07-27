"""
modules/hf/autonomous_equity_pm.py

Stock HF-4 — Autonomous Equity Portfolio Manager.

Turns HF-1 committee decisions, HF-2 analyst views, and HF-3 portfolio construction
into an autonomous portfolio management loop:
    Observe → Score → Decide → Allocate → Rebalance → Monitor → Learn
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import math
import pandas as pd


@dataclass
class PMDecision:
    symbol: str
    action: str
    target_weight: float
    current_weight: float
    confidence: float
    reason: str
    priority: str
    guardrail_status: str = "PASS"


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        if isinstance(v, float) and math.isnan(v):
            return default
        return float(v)
    except Exception:
        return default


def autonomous_pm_cycle(
    candidates: list[dict[str, Any]] | pd.DataFrame,
    current_positions: list[dict[str, Any]] | pd.DataFrame | None = None,
    portfolio_value: float = 1_000_000,
    mode: str = "recommend_only",
    max_single_name_weight: float = 0.08,
    max_turnover: float = 0.20,
) -> dict[str, Any]:
    """
    Main autonomous PM cycle. Safe by default: recommend_only mode never executes trades.
    """
    from modules.hf.portfolio_construction_os import construct_portfolio
    from modules.hf.capital_allocation_engine import allocate_capital
    from modules.hf.portfolio_heat_engine import portfolio_heat_report
    from modules.hf.risk_budget_engine import calculate_risk_budget

    current_map = _position_weight_map(current_positions)
    candidate_rows = _normalize_rows(candidates)

    for row in candidate_rows:
        row["current_weight"] = current_map.get(str(row.get("symbol", "")).upper(), _num(row.get("current_weight")))

    target = construct_portfolio(
        candidate_rows,
        max_positions=30,
        max_single_name_weight=max_single_name_weight,
        max_sector_weight=0.30,
    )

    positions = target.get("positions") or []
    allocations = allocate_capital(portfolio_value, positions)
    heat = portfolio_heat_report(positions)
    risk = calculate_risk_budget(positions)

    decisions = []
    total_turnover = 0.0

    for p in positions:
        delta = _num(p.get("rebalance_delta"))
        total_turnover += abs(delta)
        action = _decision_action(delta)
        confidence = _confidence_from_scores(p)

        guardrail = "PASS"
        if _num(p.get("target_weight")) > max_single_name_weight:
            guardrail = "FAIL_SINGLE_NAME_LIMIT"
        if total_turnover > max_turnover:
            guardrail = "WARN_TURNOVER_LIMIT"

        decisions.append(asdict(PMDecision(
            symbol=str(p.get("symbol", "")).upper(),
            action=action,
            target_weight=_num(p.get("target_weight")),
            current_weight=_num(p.get("current_weight")),
            confidence=confidence,
            reason=_decision_reason(p, delta),
            priority=_priority(delta, confidence),
            guardrail_status=guardrail,
        )))

    portfolio_action = "REBALANCE_RECOMMENDED" if any(d["action"] != "Hold" for d in decisions) else "NO_ACTION"

    return {
        "mode": mode,
        "portfolio_value": portfolio_value,
        "portfolio_action": portfolio_action,
        "turnover_estimate": round(total_turnover, 4),
        "guardrail_status": "PASS" if all(d["guardrail_status"] == "PASS" for d in decisions) else "REVIEW",
        "target_portfolio": target,
        "capital_allocation": allocations,
        "portfolio_heat": heat,
        "risk_budget": risk,
        "decisions": decisions,
        "audit_note": "HF-4 PM cycle generated recommendations only. Execution requires explicit approval.",
    }


def _normalize_rows(data: list[dict[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, pd.DataFrame):
        return data.to_dict("records")
    return [dict(x) for x in data if isinstance(x, dict)]


def _position_weight_map(data: list[dict[str, Any]] | pd.DataFrame | None) -> dict[str, float]:
    rows = _normalize_rows(data)
    out = {}
    for row in rows:
        sym = str(row.get("symbol") or row.get("ticker") or "").upper()
        if sym:
            out[sym] = _num(row.get("weight"), _num(row.get("current_weight")))
    return out


def _decision_action(delta: float) -> str:
    if delta >= 0.03:
        return "Add"
    if delta >= 0.01:
        return "Increase"
    if delta <= -0.03:
        return "Reduce"
    if delta <= -0.01:
        return "Trim"
    return "Hold"


def _confidence_from_scores(row: dict[str, Any]) -> float:
    alpha = _num(row.get("alpha_score"), 50)
    risk = _num(row.get("risk_score"), 50)
    conviction = _num(row.get("conviction_score"), 50)
    score = alpha * 0.45 + conviction * 0.35 + (100 - risk) * 0.20
    return round(max(0, min(100, score)), 1)


def _priority(delta: float, confidence: float) -> str:
    if abs(delta) >= 0.04 and confidence >= 70:
        return "High"
    if abs(delta) >= 0.02 and confidence >= 60:
        return "Medium"
    return "Low"


def _decision_reason(row: dict[str, Any], delta: float) -> str:
    action = _decision_action(delta)
    return (
        f"{action} based on alpha score {row.get('alpha_score')}, "
        f"conviction {row.get('conviction_score')}, risk {row.get('risk_score')}, "
        f"and target/current weight delta {delta:.1%}."
    )


def decisions_frame(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result.get("decisions") or [])
