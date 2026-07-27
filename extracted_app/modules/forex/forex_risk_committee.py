"""
modules/forex/forex_risk_committee.py

Phase 18B — Institutional risk committee.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ForexRiskCommittee:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def review_queue(self, decisions: List[Dict[str, Any]], snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_trade_gatekeeper import get_forex_trade_gatekeeper
        gatekeeper = get_forex_trade_gatekeeper(db=self.db)
        rows = []
        for decision in decisions:
            review = gatekeeper.review(decision, snapshot=snapshot)
            rows.append({
                "trade": decision,
                "risk_review": review,
                "risk_committee_decision": "APPROVE" if review.get("approved") and decision.get("decision") == "APPROVE" else "HOLD" if review.get("approved") else "REJECT",
            })
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "review_count": len(rows),
            "reviews": rows,
        }


_ENGINE = None


def get_forex_risk_committee(db: Optional[Any] = None) -> ForexRiskCommittee:
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE = ForexRiskCommittee(db=db)
    return _ENGINE
