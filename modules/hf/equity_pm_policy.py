"""
modules/hf/equity_pm_policy.py

Policy and approval rules for HF-4 Autonomous Equity PM.
"""
from __future__ import annotations
from typing import Any


DEFAULT_PM_POLICY = {
    "max_single_name_weight": 0.08,
    "max_sector_weight": 0.30,
    "max_turnover_per_cycle": 0.20,
    "max_daily_trades": 25,
    "require_approval_for_rebalance": True,
    "allow_auto_execution": False,
    "min_confidence_to_add": 60,
    "min_confidence_to_reduce": 45,
}


def evaluate_pm_policy(decision: dict[str, Any], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    policy = {**DEFAULT_PM_POLICY, **(policy or {})}

    reasons = []
    status = "APPROVED"

    if float(decision.get("target_weight") or 0) > policy["max_single_name_weight"]:
        status = "REJECTED"
        reasons.append("Target weight exceeds max single-name policy.")

    if decision.get("action") in {"Add", "Increase"} and float(decision.get("confidence") or 0) < policy["min_confidence_to_add"]:
        status = "REVIEW"
        reasons.append("Add/Increase confidence below policy threshold.")

    if policy.get("require_approval_for_rebalance", True) and decision.get("action") != "Hold":
        if status == "APPROVED":
            status = "REVIEW"
        reasons.append("Rebalance requires human approval.")

    return {
        "symbol": decision.get("symbol"),
        "action": decision.get("action"),
        "policy_status": status,
        "reasons": reasons or ["Within PM policy."],
    }


def evaluate_decision_set(decisions: list[dict[str, Any]], policy: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = [evaluate_pm_policy(d, policy) for d in decisions or []]
    return {
        "approved": [r for r in rows if r["policy_status"] == "APPROVED"],
        "review": [r for r in rows if r["policy_status"] == "REVIEW"],
        "rejected": [r for r in rows if r["policy_status"] == "REJECTED"],
        "all": rows,
    }
