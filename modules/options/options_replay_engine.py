"""Trade replay and post-trade review helpers."""
from __future__ import annotations
from typing import Any


def build_trade_replay(record: dict[str, Any]) -> dict[str, Any]:
    pnl = float(record.get("pnl") or 0)
    if pnl > 0:
        outcome = "Winner"
        diagnosis = "Trade thesis worked or exit captured favorable movement."
    elif pnl < 0:
        outcome = "Loser"
        diagnosis = "Trade thesis failed, timing was early/late, or risk was not controlled."
    else:
        outcome = "Flat"
        diagnosis = "Outcome was neutral; review opportunity cost and capital usage."
    return {
        "trade_id": record.get("id"),
        "ticker": record.get("ticker"),
        "strategy": record.get("strategy"),
        "outcome": outcome,
        "pnl": pnl,
        "thesis": record.get("thesis", ""),
        "diagnosis": diagnosis,
        "review_questions": [
            "Was the entry aligned with smart money flow?",
            "Was dealer positioning supportive or hostile?",
            "Was IV rank favorable for the structure?",
            "Was the exit plan defined before entry?",
        ],
    }


def replay_batch(records: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    return [build_trade_replay(r) for r in (records or [])[:limit]]
