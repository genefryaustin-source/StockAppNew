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
        """
        Real market overview used only as a fallback path (forex_terminal_api
        tries forex_portfolio_engine first and only reaches this class if
        that raises). Previously this always returned a fixed
        market_regime="RISK-OFF"/macro_score=78, regardless of real
        conditions, so any transient portfolio-engine failure would silently
        surface a fabricated "RISK-OFF" reading as if it were live. This now
        computes a real regime from forex_macro_regime_engine and real
        provider health, and honestly reports "UNKNOWN"/unavailable when
        those aren't reachable either.
        """
        regime = "UNKNOWN"
        macro_score = 0.0
        regime_status = "ERROR"
        try:
            from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
            regime_data = get_forex_macro_regime_engine().analyze()
            if isinstance(regime_data, dict):
                regime = str(
                    regime_data.get("macro_regime")
                    or regime_data.get("market_regime")
                    or regime_data.get("regime")
                    or "UNKNOWN"
                )
                macro_score = float(
                    regime_data.get("macro_score")
                    or regime_data.get("score")
                    or 0.0
                )
                regime_status = "READY"
        except Exception:
            pass

        provider_health = {}
        try:
            from modules.forex.forex_provider_health import get_forex_provider_health
            provider_health = get_forex_provider_health().summary()
        except Exception:
            provider_health = {}

        risk_appetite = "Low" if "OFF" in regime.upper() else "High" if "ON" in regime.upper() else "Unknown"
        liquidity = "Constrained" if "OFF" in regime.upper() else "Normal" if "ON" in regime.upper() else "Unknown"

        return {
            "status": regime_status,
            "workspace": "Market Overview",

            "market_regime": regime,
            "macro_score": macro_score,
            "risk_appetite": risk_appetite,
            "liquidity": liquidity,

            "provider_health": provider_health if isinstance(provider_health, dict) else {},

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