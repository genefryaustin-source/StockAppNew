"""
modules/forex/forex_suite.py

Master facade exposing the complete Forex subsystem to StockApp.
"""

from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_application_module import get_forex_application_module
from modules.forex.forex_plugin import get_forex_plugin
from modules.forex.forex_platform_service import get_forex_platform_service


class ForexSuite:
    VERSION="1.0.0"

    def __init__(self, db=None):
        self.db=db
        self.module=get_forex_application_module(db=db)
        self.plugin=get_forex_plugin(db=db)
        self.service=get_forex_platform_service(db=db)

    def initialize(self):
        return self.module.load()

    def shutdown(self):
        return self.module.unload()

    def reload(self):
        return self.module.reload()

    def metadata(self):
        return {
            "suite":"ForexSuite",
            "version":self.VERSION,
            "generated_at":datetime.now(timezone.utc).isoformat(),
            "module":self.module.metadata(),
            "plugin":self.plugin.metadata(),
        }

    def health(self):
        return self.service.health()

    def snapshot(self):
        return self.service.snapshot()

    def status(self):
        return {
            "status":"READY",
            "metadata":self.metadata(),
            "health":self.health(),
        }


_SUITE=None

def get_forex_suite(db=None):
    global _SUITE
    if _SUITE is None or (db is not None and _SUITE.db is None):
        _SUITE=ForexSuite(db=db)
    return _SUITE
