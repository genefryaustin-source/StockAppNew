"""
modules/forex/forex_ai_deal_room.py

Phase 18D — Institutional AI Deal Room.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexAIDealRoom:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def review_queue(self, trades: List[Dict[str, Any]], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_trade_review_engine import get_forex_trade_review_engine
        reviewer = get_forex_trade_review_engine(db=self.db)
        reviews = [reviewer.review(trade, snapshot=snapshot) for trade in trades]
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_count": len(reviews),
            "reviews": reviews,
            "approved": [r for r in reviews if r.get("vote", {}).get("decision") == "APPROVE"],
            "held": [r for r in reviews if r.get("vote", {}).get("decision") == "HOLD"],
            "rejected": [r for r in reviews if r.get("vote", {}).get("decision") == "REJECT"],
        }


_ENGINE = None


def get_forex_ai_deal_room(db: Optional[Any] = None) -> ForexAIDealRoom:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexAIDealRoom(db=db)
    return _ENGINE
