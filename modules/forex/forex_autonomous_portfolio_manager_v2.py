"""
modules/forex/forex_autonomous_portfolio_manager_v2.py

Phase 14E — Autonomous portfolio manager v2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAutonomousPortfolioManagerV2:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def daily_review(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_ai_investment_committee import get_forex_ai_investment_committee
        committee = get_forex_ai_investment_committee(db=self.db).review(snapshot=snapshot)
        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "committee": committee,
            "suggested_rebalances": committee.get("approved_ideas", [])[:3],
            "suggested_hedges": ["Review USD aggregate exposure", "Review JPY shock sensitivity"],
            "trade_approval_workflow": "paper_approval_required",
        }


_AUTO2 = None


def get_forex_autonomous_portfolio_manager_v2(db: Optional[Any] = None) -> ForexAutonomousPortfolioManagerV2:
    global _AUTO2
    if _AUTO2 is None or (db is not None and _AUTO2.db is None):
        _AUTO2 = ForexAutonomousPortfolioManagerV2(db=db)
    return _AUTO2
