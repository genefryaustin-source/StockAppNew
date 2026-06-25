"""
modules/forex/forex_sdk.py

SDK facade for external modules and future REST/API endpoints.
"""

from __future__ import annotations

from modules.forex.forex_api import get_forex_api


class ForexSDK:

    def __init__(self):
        self.api = get_forex_api()

    def initialize(self):
        return self.api.initialize()

    def shutdown(self):
        return self.api.shutdown()

    def refresh(self):
        return self.api.refresh()

    def dashboard(self):
        return self.api.get_dashboard_data()

    def command_center(self):
        return self.api.get_command_center()

    def opportunities(self):
        return self.api.get_top_opportunities()

    def strength(self):
        return self.api.get_currency_strength()

    def macro(self):
        return self.api.get_market_regime()

    def carry(self):
        return self.api.get_carry_trades()

    def institutional(self):
        return self.api.get_institutional_flow()

    def central_banks(self):
        return self.api.get_central_banks()

    def sentiment(self):
        return self.api.get_sentiment()

    def portfolio(self):
        return self.api.get_portfolio_summary()

    def render(self):
        self.api.render()


_SDK=None

def get_forex_sdk():
    global _SDK
    if _SDK is None:
        _SDK=ForexSDK()
    return _SDK
