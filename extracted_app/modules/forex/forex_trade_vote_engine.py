"""
modules/forex/forex_trade_vote_engine.py

Phase 18D — Institutional trade vote engine.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexTradeVoteEngine:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def vote(self, trade: Dict[str, Any], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        score = float(trade.get("institutional_score") or trade.get("confidence") or 0)
        risk_ok = score >= 60
        votes = [
            {"member": "Quant Research", "vote": "APPROVE" if score >= 65 else "HOLD"},
            {"member": "Macro Research", "vote": "APPROVE" if score >= 60 else "HOLD"},
            {"member": "AI Research", "vote": "APPROVE" if score >= 70 else "HOLD"},
            {"member": "Risk", "vote": "APPROVE" if risk_ok else "REJECT"},
            {"member": "Portfolio Manager", "vote": "APPROVE" if score >= 75 else "HOLD"},
            {"member": "Execution", "vote": "APPROVE" if score >= 60 else "HOLD"},
        ]
        approvals = sum(1 for v in votes if v["vote"] == "APPROVE")
        rejects = sum(1 for v in votes if v["vote"] == "REJECT")
        decision = "REJECT" if rejects else "APPROVE" if approvals >= 4 else "HOLD"
        return {
            "status": "READY",
            "decision": decision,
            "approvals": approvals,
            "rejects": rejects,
            "votes": votes,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


_ENGINE = None


def get_forex_trade_vote_engine(db: Optional[Any] = None) -> ForexTradeVoteEngine:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexTradeVoteEngine(db=db)
    return _ENGINE
