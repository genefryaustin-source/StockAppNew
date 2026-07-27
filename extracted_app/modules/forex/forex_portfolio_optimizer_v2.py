"""
modules/forex/forex_portfolio_optimizer_v2.py

Phase 14B — Institutional portfolio optimizer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexPortfolioOptimizerV2:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def optimize(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine
        from modules.forex.forex_risk_budget_engine import get_forex_risk_budget_engine
        from modules.forex.forex_correlation_engine import get_forex_correlation_engine

        research = get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot)
        ideas = research["alpha_research"]["ideas"]
        budget = get_forex_risk_budget_engine(db=self.db).allocate_budget(ideas)
        corr = get_forex_correlation_engine(db=self.db).matrix()

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "method": "risk_budgeted_factor_allocation",
            "research": research,
            "risk_budget": budget,
            "correlation": corr,
            "recommendation": "Use approved signals with capped risk budgets and correlation review.",
        }


_OPTIMIZER = None


def get_forex_portfolio_optimizer_v2(db: Optional[Any] = None) -> ForexPortfolioOptimizerV2:
    global _OPTIMIZER
    if _OPTIMIZER is None or (db is not None and _OPTIMIZER.db is None):
        _OPTIMIZER = ForexPortfolioOptimizerV2(db=db)
    return _OPTIMIZER
