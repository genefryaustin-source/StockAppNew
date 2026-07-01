"""
modules/forex/forex_trade_review_engine.py

Phase 18D — Trade review engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexTradeReviewEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def review(self, trade: Dict[str, Any], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_trade_vote_engine import get_forex_trade_vote_engine
        vote = get_forex_trade_vote_engine(db=self.db).vote(trade, snapshot=snapshot)
        return {
            "status": "READY",
            "trade": trade,
            "vote": vote,
            "rationale": f"Trade reviewed by AI Deal Room. Final decision: {vote.get('decision')}.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_trade_review_engine(db: Optional[Any] = None) -> ForexTradeReviewEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeReviewEngine(db=db)
    return _ENGINE
