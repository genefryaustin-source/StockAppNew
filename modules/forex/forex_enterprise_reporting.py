"""
modules/forex/forex_enterprise_reporting.py

Phase 14G — Enterprise reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


class ForexEnterpriseReporting:
    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def report_pack(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from modules.forex.forex_quant_research_engine import get_forex_quant_research_engine
        from modules.forex.forex_portfolio_optimizer_v2 import get_forex_portfolio_optimizer_v2
        from modules.forex.forex_strategy_lab_v2 import get_forex_strategy_lab_v2

        return {
            "status": "READY",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "daily_desk_report": self._report("Daily Desk Report"),
            "weekly_fx_report": self._report("Weekly FX Report"),
            "risk_report": self._report("Risk Report"),
            "execution_quality_report": self._report("Execution Quality Report"),
            "ai_decision_report": self._report("AI Decision Report"),
            "quant_research": get_forex_quant_research_engine(db=self.db).research_dashboard(snapshot=snapshot),
            "portfolio_optimizer": get_forex_portfolio_optimizer_v2(db=self.db).optimize(snapshot=snapshot),
            "strategy_lab": get_forex_strategy_lab_v2(db=self.db).run_lab(),
        }

    def _report(self, title: str) -> Dict[str, Any]:
        return {
            "title": title,
            "summary": f"{title} generated for institutional Forex terminal.",
            "status": "READY",
        }


_REPORTS = None


def get_forex_enterprise_reporting(db: Optional[Any] = None) -> ForexEnterpriseReporting:
    global _REPORTS
    if _REPORTS is None or (db is not None and _REPORTS.db is None):
        _REPORTS = ForexEnterpriseReporting(db=db)
    return _REPORTS
