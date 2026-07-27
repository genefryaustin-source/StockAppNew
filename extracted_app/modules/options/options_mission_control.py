"""Mission control wrappers for the Phase 7 dashboard."""
from __future__ import annotations
from typing import Any
from modules.options.options_execution_orchestrator import build_execution_report


def build_mission_control(ticker: str, paper: bool = True, autopilot_level: int = 1) -> dict[str, Any]:
    from modules.options.options_autopilot import apply_autopilot_policy
    report = build_execution_report(ticker, paper=paper)
    return apply_autopilot_policy(report, autopilot_level)
