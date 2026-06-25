"""
modules/forex/forex_sdk.py

Stable public SDK for the Forex subsystem.
"""

from __future__ import annotations
from typing import Any, Dict, Optional

from modules.forex.forex_suite import get_forex_suite
from modules.forex.forex_platform_service import get_forex_platform_service
from modules.forex.forex_terminal_api import get_forex_terminal_api
from modules.forex.forex_trade_execution_engine import get_forex_trade_execution_engine
from modules.forex.forex_order_management_engine import get_forex_order_management_engine
from modules.forex.forex_portfolio_manager import get_forex_portfolio_manager
from modules.forex.forex_price_service import get_forex_price_service
from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
from modules.forex.forex_strategy_lab import get_forex_strategy_lab
from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
from modules.forex.forex_performance_analytics_engine import get_forex_performance_analytics_engine


class ForexSDK:
    """
    Public programming interface for the Forex platform.
    Keeps external callers isolated from internal module architecture.
    """

    def __init__(self, db=None):
        self.db=db
        self.suite=get_forex_suite(db=db)
        self.service=get_forex_platform_service(db=db)
        self.terminal=get_forex_terminal_api(db=db)
        self.execution=get_forex_trade_execution_engine(db=db)
        self.orders_engine=get_forex_order_management_engine(db=db)
        self.portfolio=get_forex_portfolio_manager(db=db)
        self.price_service=get_forex_price_service()
        self.strength_engine=get_forex_currency_strength_engine()
        self.sentiment_engine=get_forex_sentiment_engine()
        self.macro_engine=get_forex_macro_regime_engine()
        self.central_bank_engine=get_forex_central_bank_engine()
        self.strategy_engine=get_forex_strategy_lab(db=db)
        self.alpha_engine=get_forex_alpha_model()
        self.institutional_engine=get_forex_institutional_scanner()
        self.performance_engine=get_forex_performance_analytics_engine(db=db)

    # Platform Lifecycle
    def initialize(self): return self.suite.initialize()
    def shutdown(self): return self.suite.shutdown()
    def reload(self): return self.suite.reload()
    def status(self): return self.suite.status()
    def health(self): return self.suite.health()

    # Trading API
    def submit_order(self, **kwargs): return self.execution.submit_order(**kwargs)
    def cancel_order(self, broker_order_id): return self.orders_engine.cancel(broker_order_id)

    def modify_order(self, broker_order_id:str, **updates):
        return {
            "status":"unsupported",
            "broker_order_id":broker_order_id,
            "message":"Order modification is not enabled; cancel and replace instead.",
            "updates":updates,
        }

    def close_position(self, pair:str, units:Optional[float]=None, **kwargs):
        side=kwargs.pop("side","SELL")
        qty=units if units is not None else kwargs.pop("units",10000)
        return self.submit_order(pair=pair, side=side, units=qty, **kwargs)

    # Portfolio API
    def portfolio_summary(self, **kwargs): return self.portfolio.portfolio_summary(**kwargs)
    def positions(self, **kwargs): return self.portfolio.mark_positions(**kwargs)
    def orders(self): return {"open":self.orders_engine.open_orders(),"filled":self.orders_engine.filled_orders()}
    def trade_history(self): return self.orders_engine.filled_orders()

    # Market Data API
    def quotes(self, pairs, force_refresh:bool=False):
        if isinstance(pairs,str):
            return self.price_service.get_quote(pairs, force_refresh=force_refresh)
        return self.price_service.get_quotes(pairs, force_refresh=force_refresh)

    def currency_strength(self): return self.strength_engine.command_center_payload()
    def sentiment(self): return self.sentiment_engine.analyze()
    def macro_regime(self): return self.macro_engine.analyze()
    def central_bank_events(self): return self.central_bank_engine.analyze()

    # Analytics API
    def strategy_lab(self): return self.strategy_engine.run()
    def alpha_model(self): return self.alpha_engine.command_center_payload()
    def institutional_flow(self): return self.institutional_engine.scan()
    def performance(self, **kwargs): return self.performance_engine.analyze(**kwargs)

    # Administration API
    def validate(self): return self.service.validate()
    def benchmark(self): return self.service.gateway.platform.benchmark()
    def stress_test(self): return self.service.gateway.platform.stress_test()
    def production_readiness(self): return self.service.gateway.platform.production_readiness()

    # Enterprise API
    def enterprise_snapshot(self): return self.service.snapshot()
    def deployment_status(self): return self.service.gateway.platform.deployment.deployment_status()
    def platform_metadata(self): return self.service.metadata()


_SDK=None

def get_forex_sdk(db=None)->ForexSDK:
    global _SDK
    if _SDK is None or (db is not None and _SDK.db is None):
        _SDK=ForexSDK(db=db)
    return _SDK
