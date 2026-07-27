"""
modules/forex/forex_registry.py
"""

from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_command_center_engine import get_forex_command_center_engine
from modules.forex.forex_currency_strength_engine import get_forex_currency_strength_engine
from modules.forex.forex_alpha_model import get_forex_alpha_model
from modules.forex.forex_carry_trade_engine import get_forex_carry_trade_engine
from modules.forex.forex_central_bank_engine import get_forex_central_bank_engine
from modules.forex.forex_sentiment_engine import get_forex_sentiment_engine
from modules.forex.forex_macro_regime_engine import get_forex_macro_regime_engine
from modules.forex.forex_institutional_scanner import get_forex_institutional_scanner
from modules.forex.forex_price_service import get_forex_price_service
from modules.forex.providers.forex_provider_router import get_forex_provider_router


class ForexRegistry:

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

        self.engines = {}
        self.services = {}
        self.providers = {}
        self.dashboards = {}

    def bootstrap(self):
        self.services["price_service"] = get_forex_price_service()

        self.services["provider_router"] = get_forex_provider_router()

        self.engines.update({
            "command_center": get_forex_command_center_engine(),
            "currency_strength": get_forex_currency_strength_engine(),
            "alpha": get_forex_alpha_model(),
            "carry_trade": get_forex_carry_trade_engine(),
            "central_bank": get_forex_central_bank_engine(),
            "macro_regime": get_forex_macro_regime_engine(),
            "institutional": get_forex_institutional_scanner(),
            "sentiment": get_forex_sentiment_engine(),
        })

        try:
            router=self.services["provider_router"]
            if hasattr(router,"providers"):
                self.providers=router.providers
            elif hasattr(router,"all_providers"):
                self.providers={p.provider_name():p for p in router.all_providers()}
        except Exception:
            self.providers={}

        return self

    def register_engine(self,name:str,obj:Any):
        self.engines[name]=obj

    def register_service(self,name:str,obj:Any):
        self.services[name]=obj

    def register_provider(self,name:str,obj:Any):
        self.providers[name]=obj

    def register_dashboard(self,name:str,obj:Any):
        self.dashboards[name]=obj

    def get_engine(self,name:str):
        return self.engines.get(name)

    def get_service(self,name:str):
        return self.services.get(name)

    def get_provider(self,name:str):
        return self.providers.get(name)

    def get_dashboard(self,name:str):
        return self.dashboards.get(name)

    def summary(self):
        return {
            "engines": sorted(self.engines.keys()),
            "services": sorted(self.services.keys()),
            "providers": sorted(self.providers.keys()),
            "dashboards": sorted(self.dashboards.keys()),
        }


_REGISTRY = None

def get_forex_registry(
    db=None,
    tenant_id=None,
    user_id=None,
    portfolio_id=None,
):
    global _REGISTRY

    if (
        _REGISTRY is None
        or getattr(_REGISTRY, "db", None) is not db
        or getattr(_REGISTRY, "tenant_id", None) != tenant_id
        or getattr(_REGISTRY, "user_id", None) != user_id
        or getattr(_REGISTRY, "portfolio_id", None) != portfolio_id
    ):

        _REGISTRY = ForexRegistry(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        ).bootstrap()

    return _REGISTRY
