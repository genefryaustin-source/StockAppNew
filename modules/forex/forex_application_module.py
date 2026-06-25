"""
modules/forex/forex_application_module.py

Top-level application module wrapper for StockApp.
"""
from __future__ import annotations
from datetime import datetime, timezone

from modules.forex.forex_application_descriptor import (
    get_forex_application_descriptor,
    initialize_application,
    shutdown_application,
    application_health,
    application_metadata,
)

class ForexApplicationModule:
    def __init__(self, db=None):
        self.db=db

    def load(self):
        return initialize_application(db=self.db)

    def unload(self):
        return shutdown_application()

    def reload(self):
        self.unload()
        return self.load()

    def descriptor(self):
        return get_forex_application_descriptor()

    def metadata(self):
        return application_metadata()

    def health(self):
        return application_health()

    def status(self):
        return {
            "module":"Forex",
            "state":"READY",
            "timestamp":datetime.now(timezone.utc).isoformat(),
            "health":self.health(),
        }

_MODULE=None

def get_forex_application_module(db=None):
    global _MODULE
    if _MODULE is None or (db is not None and _MODULE.db is None):
        _MODULE=ForexApplicationModule(db=db)
    return _MODULE
