"""Watchtower: combines signals, alerts, and opportunities for the dashboard."""
from __future__ import annotations
from typing import Any


def build_watchtower_snapshot(execution_report: dict[str, Any]) -> dict[str, Any]:
    signals = execution_report.get("signals", {})
    alerts = execution_report.get("alerts", [])
    queue = execution_report.get("trade_queue", [])
    return {
        "ticker": execution_report.get("ticker"),
        "signal_score": signals.get("combined_signal_score", 50),
        "direction": signals.get("direction", "Neutral"),
        "open_alerts": len(alerts),
        "queued_trades": len(queue),
        "approved_trades": len([q for q in queue if q.get("guardrail_status") == "approved"]),
        "blocked_trades": len([q for q in queue if q.get("guardrail_status") == "blocked"]),
        "state": "Actionable" if len(queue) else "Monitoring",
    }
