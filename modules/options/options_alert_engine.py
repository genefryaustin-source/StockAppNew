"""Phase 7 options alert engine."""
from __future__ import annotations
from typing import Any


def generate_execution_alerts(report: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    signals = report.get("signals", {})
    queue = report.get("trade_queue", [])
    score = float(signals.get("combined_signal_score") or 50)
    if score >= 75:
        alerts.append({"severity": "HIGH", "type": "High Conviction Opportunity", "message": "Combined signal score is elevated."})
    if score <= 25:
        alerts.append({"severity": "HIGH", "type": "Bearish Conviction Opportunity", "message": "Combined signal score is sharply bearish."})
    blocked = [q for q in queue if q.get("guardrail_status") == "blocked"]
    if blocked:
        alerts.append({"severity": "MEDIUM", "type": "Guardrail Blocks", "message": f"{len(blocked)} trade candidate(s) blocked by guardrails."})
    if not alerts:
        alerts.append({"severity": "INFO", "type": "No Critical Alerts", "message": "No urgent execution alert currently active."})
    return alerts
