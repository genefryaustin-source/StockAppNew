"""
modules/forex/forex_institutional_terminal.py

Institutional Forex terminal facade.
"""

from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_terminal_dashboard import get_forex_terminal_dashboard
from modules.forex.forex_trading_desk import get_forex_trading_desk
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_ai_assistant import get_forex_ai_assistant


class ForexInstitutionalTerminal:
    VERSION = "1.0.0"

    def __init__(self, db=None):
        self.db = db
        self.dashboard = get_forex_terminal_dashboard(db=db)
        self.trading_desk = get_forex_trading_desk(db=db)
        self.portfolio = get_forex_portfolio_manager(db=db)
        self.ai = get_forex_ai_assistant(db=db)

    def dashboard_view(self):
        return self.dashboard.render() if hasattr(self.dashboard, "render") else self.dashboard

    def snapshot(
            self,
            db=None,
            refresh=False,
    ):
        market = self.market_overview()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),

            "status": "READY",

            "market_overview": market,

            "terminal": {
                "name": "Institutional",
                "status": "READY",
                "market_overview": market,
            },

            "portfolio": (
                self.portfolio.portfolio_summary()
                if hasattr(self.portfolio, "portfolio_summary")
                else {}
            ),
        }

    def market_overview(self):
        return {
            "status": "READY",
            "workspace": "Market Overview",

            "market_regime": "RISK-OFF",
            "macro_score": 78,
            "risk_appetite": "Low",
            "liquidity": "Constrained",

            "provider_health": {},

            "alerts": [],

            "economic_calendar": [],

            "ai_summary": "",

            "execution_health": {},
        }

    def trading_workspace(self):
        return self.trading_desk

    def portfolio_workspace(self):
        return self.portfolio

    def institutional_workspace(self):
        return {
            "terminal": "Institutional",
            "dashboard": self.dashboard,
            "trading": self.trading_desk,
            "portfolio": self.portfolio,
        }

    def ai_workspace(self):
        return self.ai

    def status(self):
        return {
            "terminal": "Forex Institutional Terminal",
            "version": self.VERSION,
            "status": "READY",
        }


_INSTANCE = None


def get_forex_institutional_terminal(db=None):
    global _INSTANCE
    if _INSTANCE is None or (db is not None and _INSTANCE.db is None):
        _INSTANCE = ForexInstitutionalTerminal(db=db)
    return _INSTANCE
