"""
modules/forex/forex_institutional_command_center_v2.py

Phase 14F — Institutional AI & Quant command center.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexInstitutionalCommandCenterV2:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def dashboard(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine
        from modules.forex.forex_portfolio_optimizer_v2 import get_forex_portfolio_optimizer_v2
        from modules.forex.forex_strategy_lab_v2 import get_forex_strategy_lab_v2
        from modules.forex.forex_ai_investment_committee import get_forex_ai_investment_committee
        from modules.forex.forex_enterprise_reporting import get_forex_enterprise_reporting

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "quant_research": get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot),
            "portfolio_optimizer": get_forex_portfolio_optimizer_v2(db=self.db).optimize(snapshot=snapshot),
            "strategy_lab": get_forex_strategy_lab_v2(db=self.db).run_lab(),
            "ai_investment_committee": get_forex_ai_investment_committee(db=self.db).review(snapshot=snapshot),
            "enterprise_reporting": get_forex_enterprise_reporting(db=self.db).report_pack(snapshot=snapshot),
        }


_CENTER2 = None


def get_forex_institutional_command_center_v2(db: Optional[Any] = None) -> ForexInstitutionalCommandCenterV2:
    global _CENTER2
    if _CENTER2 is None or (db is not None and _CENTER2.db is None):
        _CENTER2 = ForexInstitutionalCommandCenterV2(db=db)
    return _CENTER2
