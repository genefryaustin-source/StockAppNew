"""
modules/forex/forex_ai_investment_committee.py

Phase 14E — AI investment committee.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexAIInvestmentCommittee:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def review(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_portfolio_optimizer_v2 import get_forex_portfolio_optimizer_v2
        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine

        research = get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot)
        optimizer = get_forex_portfolio_optimizer_v2(db=self.db).optimize(snapshot=snapshot)

        approved = [
            idea for idea in research["alpha_research"]["ideas"]
            if idea["alpha_score"] >= 60 and idea["signal"] in {"BUY", "SELL"}
        ]

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "decision": "APPROVE_PAPER_TRADES" if approved else "HOLD",
            "approved_ideas": approved[:5],
            "research": research,
            "optimizer": optimizer,
            "committee_notes": [
                "Paper trading approval only.",
                "Live execution requires broker safety configuration.",
                "Risk budget must be respected.",
            ],
        }


_COMMITTEE = None


def get_forex_ai_investment_committee(db: Optional[Any] = None) -> ForexAIInvestmentCommittee:
    global _COMMITTEE
    if _COMMITTEE is None or (db is not None and _COMMITTEE.db is None):
        _COMMITTEE = ForexAIInvestmentCommittee(db=db)
    return _COMMITTEE
