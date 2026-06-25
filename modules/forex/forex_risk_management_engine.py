"""
modules/forex/forex_risk_management_engine.py
"""

from __future__ import annotations

from typing import Dict, Any

from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager


class ForexRiskManagementEngine:

    def __init__(self, db=None):
        self.db=db
        self.portfolio=get_forex_portfolio_manager(db=db)

    def analyze(self, **kwargs)->Dict[str,Any]:
        summary=self.portfolio.portfolio_summary(**kwargs)
        risk=summary.get("risk",{})
        exposure=summary.get("currency_exposure",{})

        alerts=[]
        if risk.get("concentration_pct",0)>=40:
            alerts.append("Portfolio concentration exceeds threshold.")

        if abs(risk.get("portfolio_pnl",0))>5000:
            alerts.append("Large unrealized P&L swing detected.")

        for ccy,val in exposure.items():
            if abs(val)>250000:
                alerts.append(f"Large {ccy} exposure.")

        return {
            "summary":summary,
            "risk":risk,
            "currency_exposure":exposure,
            "alerts":alerts,
            "risk_level":"HIGH" if alerts else "NORMAL",
        }

_ENGINE=None

def get_forex_risk_management_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE=ForexRiskManagementEngine(db=db)
    return _ENGINE
