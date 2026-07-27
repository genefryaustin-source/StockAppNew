"""
modules/forex/forex_trade_priority_engine.py

Phase 18A — Trade priority ranking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexTradePriorityEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def prioritize(self, decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows = []
        for d in decisions:
            score = float(d.get("institutional_score") or d.get("score", {}).get("institutional_score") or 0)
            conviction = float(d.get("conviction_score") or d.get("conviction", {}).get("conviction_score") or 0)
            risk_penalty = 0 if str(d.get("decision") or d.get("decision_bias")).upper() == "APPROVE" else 10
            priority = score * 0.65 + conviction * 0.35 - risk_penalty
            row = dict(d)
            row["priority_score"] = round(priority, 2)
            rows.append(row)

        rows.sort(key=lambda r: r["priority_score"], reverse=True)

        return {
            "status": "READY",
            "trade_count": len(rows),
            "ranked_trades": rows,
            "top_trade": rows[0] if rows else {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_trade_priority_engine(db: Optional[Any] = None) -> ForexTradePriorityEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradePriorityEngine(db=db)
    return _ENGINE
