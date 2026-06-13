"""Governance and approval guardrails for autonomous PM."""
from __future__ import annotations
from typing import Any

DEFAULT_GUARDRAILS = {
    "max_autonomous_level": 2,
    "max_single_trade_pct": 3.0,
    "max_daily_new_risk_pct": 8.0,
    "require_human_approval_for_live_orders": True,
    "block_earnings_unless_approved": True,
    "block_level_5_autopilot": True,
}


def evaluate_governance(trades: list[dict[str, Any]], autopilot_level: int = 1, guardrails: dict[str, Any] | None = None) -> dict[str, Any]:
    g = {**DEFAULT_GUARDRAILS, **(guardrails or {})}
    blocked = []
    approved = []
    for trade in trades:
        if autopilot_level > int(g["max_autonomous_level"]):
            blocked.append({**trade, "block_reason": "Autopilot level exceeds policy."})
        elif float(trade.get("size_pct", 0)) > float(g["max_single_trade_pct"]):
            blocked.append({**trade, "block_reason": "Trade size exceeds max single-trade limit."})
        else:
            approved.append({**trade, "approval_status": "Queue for review" if g["require_human_approval_for_live_orders"] else "Approved"})
    return {"guardrails": g, "approved": approved, "blocked": blocked, "autopilot_level": autopilot_level}
