"""Autopilot level definitions and decision gates."""
from __future__ import annotations
from typing import Any

AUTOPILOT_LEVELS = {
    0: "Manual",
    1: "AI Recommendations",
    2: "Trade Queue Automation",
    3: "Auto Strategy Generation",
    4: "Auto Approval Rules",
    5: "Fully Autonomous Execution",
}


def autopilot_policy(level: int) -> dict[str, Any]:
    level = int(level)
    return {
        "level": level,
        "label": AUTOPILOT_LEVELS.get(level, "Manual"),
        "generate_recommendations": level >= 1,
        "queue_trades": level >= 2,
        "auto_generate": level >= 3,
        "auto_approve": level >= 4,
        "live_execution_allowed": False if level < 5 else False,
        "note": "Live execution remains disabled by default; Level 5 requires explicit broker-side approval wiring.",
    }


def apply_autopilot_policy(report: dict[str, Any], level: int) -> dict[str, Any]:
    policy = autopilot_policy(level)
    out = dict(report)
    out["autopilot"] = policy
    if not policy["queue_trades"]:
        out["routes"] = []
    return out
