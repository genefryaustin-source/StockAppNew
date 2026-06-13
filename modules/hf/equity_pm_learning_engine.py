"""
modules/hf/equity_pm_learning_engine.py

Learning loop for HF-4. Tracks PM decisions versus outcomes.
"""
from __future__ import annotations
from typing import Any
import pandas as pd


def score_pm_outcomes(decisions: list[dict[str, Any]], outcomes: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    outcomes = outcomes or []
    outcome_map = {str(o.get("symbol")).upper(): o for o in outcomes}
    rows = []

    for d in decisions or []:
        sym = str(d.get("symbol")).upper()
        outcome = outcome_map.get(sym, {})
        realized_return = float(outcome.get("realized_return") or 0)
        action = d.get("action")
        correct = (action in {"Add", "Increase"} and realized_return > 0) or (action in {"Reduce", "Trim"} and realized_return < 0) or action == "Hold"
        rows.append({
            "symbol": sym,
            "action": action,
            "confidence": d.get("confidence"),
            "realized_return": realized_return,
            "decision_correct": bool(correct),
        })

    accuracy = sum(1 for r in rows if r["decision_correct"]) / len(rows) if rows else 0
    return {
        "accuracy": round(accuracy, 3),
        "evaluated_decisions": len(rows),
        "rows": rows,
    }


def learning_frame(report: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(report.get("rows") or [])
