"""
modules/forex/forex_rest_api.py
"""

from __future__ import annotations
from modules.forex.forex_sdk import get_forex_sdk

class ForexRestAPI:
    def __init__(self,db=None):
        self.db=db
        self.sdk=get_forex_sdk(db=db)
        self._routes={
            "GET /forex/status":"status",
            "GET /forex/health":"health",
            "GET /forex/metadata":"platform_metadata",
            "GET /forex/snapshot":"enterprise_snapshot",
            "GET /forex/quotes":"quotes",
            "GET /forex/currency-strength":"currency_strength",
            "GET /forex/sentiment":"sentiment",
            "GET /forex/macro-regime":"macro_regime",
            "GET /forex/central-banks":"central_bank_events",
            "POST /forex/orders":"submit_order",
            "GET /forex/orders":"orders",
            "GET /forex/positions":"positions",
            "GET /forex/trades":"trade_history",
            "GET /forex/portfolio":"portfolio_summary",
            "GET /forex/performance":"performance",
            "GET /forex/strategy-lab":"strategy_lab",
            "GET /forex/alpha-model":"alpha_model",
            "GET /forex/institutional-flow":"institutional_flow",
            "POST /forex/validate":"validate",
            "POST /forex/benchmark":"benchmark",
            "POST /forex/stress-test":"stress_test",
            "POST /forex/production-readiness":"production_readiness",
        }

    def register_routes(self,app):
        for route,handler in self._routes.items():
            app[route]=handler
        return len(self._routes)

    def unregister_routes(self,app):
        for r in list(self._routes):
            app.pop(r,None)

    def route_count(self):
        return len(self._routes)

    def route_manifest(self):
        return {
            "service":"Forex REST API",
            "version":"1.0.0",
            "status":"READY",
            "routes":len(self._routes),
            "authenticated":True,
            "sdk":"ForexSDK",
            "api":"ForexAPI",
            "manifest":self._routes
        }

_API=None
def get_forex_rest_api(db=None):
    global _API
    if _API is None or (db is not None and _API.db is None):
        _API=ForexRestAPI(db=db)
    return _API
