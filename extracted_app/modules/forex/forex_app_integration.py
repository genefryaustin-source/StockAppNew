"""
modules/forex/forex_app_integration.py
"""
from __future__ import annotations

import streamlit as st

from modules.forex.forex_ui import render_forex_workspace
from modules.forex.forex_provider_health import get_forex_provider_health
from modules.forex.forex_price_service import get_forex_price_service
from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_carry_trade_engine import get_forex_carry_trade_engine
from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
from modules.forex.forex_command_center_engine import get_forex_command_center_engine

class ForexApplication:
    class ForexApplication:

        def __init__(
                self,
                db=None,
                tenant_id=None,
                user_id=None,
                portfolio_id=None,
        ):
            self.db = db

            self.tenant_id = tenant_id
            self.user_id = user_id
            self.portfolio_id = portfolio_id

            self.services = {}

    def initialize(self):
        self.services={
            "price_service":get_forex_price_service(),
            "provider_health":get_forex_provider_health(),
            "currency_strength":get_forex_currency_strength_engine(),
            "alpha_model":get_forex_alpha_model(),
            "carry_trade":get_forex_carry_trade_engine(),
            "central_bank":get_forex_central_bank_engine(),
            "sentiment":get_forex_sentiment_engine(),
            "macro_regime":get_forex_macro_regime_engine(),
            "institutional":get_forex_institutional_scanner(),
            "command_center":get_forex_command_center_engine(),
        }
        return self.services

    def health(self):
        try:
            h=self.services["provider_health"].summary()
            return {"status":"healthy","providers":h}
        except Exception as exc:
            return {"status":"error","error":str(exc)}

    def render(self):
        if not self.services:
            self.initialize()

        health=self.health()
        if health["status"]!="healthy":
            st.error(f"Forex initialization failed: {health.get('error')}")
            return

        render_forex_workspace(
            db=self.db,
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            portfolio_id=self.portfolio_id,
        )

_APP = None


def get_forex_application(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _APP

    if (
        _APP is None
        or getattr(_APP, "db", None) is not db
        or getattr(_APP, "tenant_id", None) != tenant_id
        or getattr(_APP, "user_id", None) != user_id
        or getattr(_APP, "portfolio_id", None) != portfolio_id
    ):

        _APP = ForexApplication(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        _APP.initialize()

    return _APP

def initialize_forex():
    return get_forex_application().initialize()

def render_forex():
    get_forex_application().render()
