"""
modules/forex/forex_service.py
"""

from __future__ import annotations

from modules.forex.forex_application import get_forex_application
from modules.forex.forex_platform_controller import get_forex_platform_controller
from modules.forex.forex_command_center_engine import get_forex_command_center_engine
from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_carry_trade_engine import get_forex_carry_trade_engine
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner


class ForexService:
    """Single public API for the Forex subsystem."""

    def __init__(self):
        self.application = get_forex_application()
        self.controller = get_forex_platform_controller()

    def initialize(self):
        return self.application.startup()

    def shutdown(self):
        return self.application.shutdown()

    def refresh_market_data(self):
        return self.application.refresh()

    def diagnostics(self):
        return self.application.diagnostics()

    def get_command_center(self):
        return get_forex_command_center_engine().build()

    def get_currency_strength(self):
        return get_forex_currency_strength_engine().command_center_payload()

    def get_alpha_recommendations(self):
        return get_forex_alpha_model().run_alpha_model()

    def get_carry_trades(self):
        return get_forex_carry_trade_engine().analyze()

    def get_macro_regime(self):
        return get_forex_macro_regime_engine().analyze()

    def get_central_bank_analysis(self):
        return get_forex_central_bank_engine().analyze()

    def get_sentiment(self):
        return get_forex_sentiment_engine().analyze()

    def get_institutional_flow(self):
        return get_forex_institutional_scanner().scan()

    def render(self):
        self.application.render()


_SERVICE=None

def get_forex_service():
    global _SERVICE
    if _SERVICE is None:
        _SERVICE=ForexService()
    return _SERVICE

def render_forex():
    get_forex_service().render()
