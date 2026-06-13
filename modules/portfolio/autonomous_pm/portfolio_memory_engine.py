"""Lightweight in-session memory for autonomous PM decisions."""
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone


def record_pm_decision(session_state: Any, ticker: str, decision: dict[str, Any]) -> None:
    key = "autonomous_pm_decisions"
    if key not in session_state:
        session_state[key] = []
    session_state[key].append({"ticker": ticker.upper(), "time": datetime.now(timezone.utc).isoformat(), "decision": decision})


def get_pm_decisions(session_state: Any, limit: int = 25) -> list[dict[str, Any]]:
    return list(session_state.get("autonomous_pm_decisions", []))[-limit:]
