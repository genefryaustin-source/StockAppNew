"""Feedback optimizer that turns learning into updated strategy weights."""
from __future__ import annotations
from typing import Any


def optimize_strategy_weights(learning_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in learning_report.get("strategy_attribution", []):
        pnl = float(item.get("total_pnl") or 0)
        wr = float(item.get("win_rate") or 0)
        score = 50 + min(25, pnl / 1000 * 10) + min(25, (wr - 50) / 50 * 25)
        score = max(0, min(100, score))
        if score >= 70:
            action = "Increase Allocation"
        elif score <= 40:
            action = "Reduce Allocation"
        else:
            action = "Maintain"
        rows.append({"strategy": item.get("strategy"), "learning_score": round(score, 1), "action": action, "basis": f"P/L={pnl:.0f}, Win Rate={wr:.1f}%"})
    return sorted(rows, key=lambda r: r["learning_score"], reverse=True)
