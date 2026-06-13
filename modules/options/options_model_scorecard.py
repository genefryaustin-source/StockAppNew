"""AI/model scorecard for options recommendations."""
from __future__ import annotations
from typing import Any


def build_model_scorecard(records: list[dict[str, Any]]) -> dict[str, Any]:
    ai_records = [r for r in records or [] if str(r.get("source", "")).lower() in {"ai", "autopilot", "sample"}]
    if not ai_records:
        return {"recommendations": 0, "accuracy": 0, "avg_pnl": 0, "status": "No AI recommendation history yet"}
    wins = [r for r in ai_records if float(r.get("pnl") or 0) > 0]
    avg = sum(float(r.get("pnl") or 0) for r in ai_records) / max(1, len(ai_records))
    acc = len(wins) / max(1, len(ai_records)) * 100
    if acc >= 65:
        label = "Strong"
    elif acc >= 50:
        label = "Developing"
    else:
        label = "Needs Calibration"
    return {"recommendations": len(ai_records), "accuracy": round(acc, 1), "avg_pnl": round(avg, 2), "status": label}


def model_improvement_actions(scorecard: dict[str, Any]) -> list[str]:
    acc = float(scorecard.get("accuracy") or 0)
    actions = []
    if acc < 50:
        actions.append("Require dealer alignment and smart-money confirmation before queueing AI trades.")
        actions.append("Increase minimum conviction threshold for autonomous trade generation.")
    elif acc < 65:
        actions.append("Keep AI recommendations in review mode until more outcome data is collected.")
    else:
        actions.append("AI recommendation quality is improving; consider limited automation under guardrails.")
    return actions
