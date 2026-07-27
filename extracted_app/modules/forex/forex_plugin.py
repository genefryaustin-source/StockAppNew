"""
modules/forex/forex_plugin.py

StockApp plugin wrapper for the Forex subsystem.
"""
from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_module_loader import (
    load_forex_module,
    unload_forex_module,
    reload_forex_module,
    module_status,
)
from modules.forex.forex_enterprise_platform import get_forex_enterprise_platform
from modules.forex.forex_platform_service import get_forex_platform_service


class ForexPlugin:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self._loaded=False
        self._service=get_forex_platform_service(db=db)
        self._platform=get_forex_enterprise_platform(db=db)

    def initialize(self, db=None):
        if db is not None:
            self.db=db
        report=load_forex_module(db=self.db)
        self._loaded=True
        return report

    def shutdown(self):
        self._loaded=False
        return unload_forex_module()

    def reload(self):
        self._loaded=True
        return reload_forex_module(db=self.db)

    def metadata(self):
        return {
            "module":"Forex",
            "display_name":"Foreign Exchange",
            "version":self.VERSION,
            "category":"Trading",
            "status":"READY",
            "enterprise":True,
            "services":18,
            "engines":14,
            "dashboards":20,
            "admin_pages":5,
            "validation_suites":6,
            "loaded":self._loaded,
            "generated_at":datetime.now(timezone.utc).isoformat(),
        }

    def health(self): return self._service.health()
    def dashboards(self): return ["Trading Desk","Terminal","Portfolio","Orders","AI","Health","Validation","Operations"]
    def workspaces(self): return ["Trader","Institutional","Enterprise","Administration"]
    def admin_pages(self): return ["Administration Suite","Operations","Health","Validation","Master Administration"]
    def api_routes(self): return ["/forex/api","/forex/orders","/forex/portfolio","/forex/terminal"]
    def scheduled_jobs(self): return ["market_refresh","sentiment_refresh","macro_refresh","health_check"]
    def validation_suites(self): return [
        "System Validation","End-to-End","Performance","Stress","Chaos","Production Readiness"
    ]
    def enterprise_platform(self): return self._platform
    def platform_service(self): return self._service
    def status(self): return module_status()

_PLUGIN=None

def get_forex_plugin(db=None):
    global _PLUGIN
    if _PLUGIN is None or (db is not None and _PLUGIN.db is None):
        _PLUGIN=ForexPlugin(db=db)
    return _PLUGIN
