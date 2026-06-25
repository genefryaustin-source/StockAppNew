"""
modules/forex/forex_performance_analytics_engine.py
"""

from __future__ import annotations

from typing import Dict, Any

from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager


class ForexPerformanceAnalyticsEngine:

    def __init__(self, db=None):
        self.db=db
        self.portfolio=get_forex_portfolio_manager(db=db)

    def analyze(self, **kwargs)->Dict[str,Any]:
        report=self.portfolio.portfolio_summary(**kwargs)
        positions=report.get("positions",[])

        pnl=[p.get("unrealized_pnl",0.0) for p in positions]
        wins=[x for x in pnl if x>0]
        losses=[x for x in pnl if x<0]

        gross_profit=sum(wins)
        gross_loss=abs(sum(losses))
        profit_factor=(gross_profit/gross_loss) if gross_loss else None

        return {
            "summary":report["summary"],
            "performance":{
                "gross_profit":round(gross_profit,2),
                "gross_loss":round(gross_loss,2),
                "net_profit":round(sum(pnl),2),
                "winning_positions":len(wins),
                "losing_positions":len(losses),
                "win_rate":round((len(wins)/max(len(positions),1))*100,2),
                "profit_factor":round(profit_factor,2) if profit_factor else None,
                "average_winner":round(gross_profit/max(len(wins),1),2),
                "average_loser":round((-gross_loss)/max(len(losses),1),2),
            },
            "positions":positions,
        }

_ENGINE=None

def get_forex_performance_analytics_engine(db=None):
    global _ENGINE
    if _ENGINE is None or (db is not None and _ENGINE.db is None):
        _ENGINE=ForexPerformanceAnalyticsEngine(db=db)
    return _ENGINE
