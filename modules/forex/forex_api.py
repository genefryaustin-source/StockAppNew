"""
modules/forex/forex_api.py
"""

from __future__ import annotations

from modules.forex.forex_service import get_forex_service

class ForexAPI:
    """Unified API facade for the Forex subsystem."""

    def __init__(self):
        self.service=get_forex_service()

    def initialize(self):
        return self.service.initialize()

    def shutdown(self):
        return self.service.shutdown()

    def refresh(self):
        return self.service.refresh_market_data()

    def get_dashboard_data(self):
        return {
            "command_center": self.service.get_command_center(),
            "macro_regime": self.service.get_macro_regime(),
            "currency_strength": self.service.get_currency_strength(),
            "top_opportunities": self.service.get_alpha_recommendations(),
            "institutional_flow": self.service.get_institutional_flow(),
            "carry_trades": self.service.get_carry_trades(),
            "central_banks": self.service.get_central_bank_analysis(),
            "sentiment": self.service.get_sentiment(),
        }

    def get_command_center(self):
        return self.service.get_command_center()

    def get_market_regime(self):
        return self.service.get_macro_regime()

    def get_currency_strength(self):
        return self.service.get_currency_strength()

    def get_top_opportunities(self):
        return self.service.get_alpha_recommendations()

    def get_institutional_flow(self):
        return self.service.get_institutional_flow()

    def get_carry_trades(self):
        return self.service.get_carry_trades()

    def get_central_banks(self):
        return self.service.get_central_bank_analysis()

    def get_sentiment(self):
        return self.service.get_sentiment()

    def get_portfolio_summary(self):
        return {
            "status":"ready",
            "message":"Connect to existing portfolio/paper trading infrastructure."
        }

    def render(self):
        self.service.render()

_API=None

def get_forex_api():
    global _API
    if _API is None:
        _API=ForexAPI()
    return _API

def render_forex():
    get_forex_api().render()
