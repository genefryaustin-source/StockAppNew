"""
modules/forex/forex_module.py

Canonical module entry point for the Forex subsystem.
"""

from __future__ import annotations

from typing import Any, Optional

from modules.forex.forex_bootstrap import get_forex_bootstrap
from modules.forex.forex_application import get_forex_application
from modules.forex.forex_app_router import get_forex_app_router
from modules.forex.forex_terminal_api import get_forex_terminal_api
from modules.forex.forex_trading_desk import get_forex_trading_desk
from modules.forex.forex_provider_health import get_forex_provider_health


class ForexModule:
    def __init__(self, db: Optional[Any] = None):
        self.db = db
        self.bootstrap = get_forex_bootstrap(db=db)
        self.application = get_forex_application(db=db)
        self.router = get_forex_app_router(db=db)
        self.terminal_api = get_forex_terminal_api(db=db)
        self.trading_desk = get_forex_trading_desk(db=db)
        self.provider_health = get_forex_provider_health()

    def initialize(self):
        return self.bootstrap.initialize()

    def render(self):
        return self.router.render()

    def refresh(self):
        return self.application.refresh()

    def shutdown(self):
        return self.bootstrap.shutdown()

    def health(self):
        try:
            return {
                "status": "healthy",
                "providers": self.provider_health.summary(),
            }
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
            }

    def snapshot(self, **kwargs):
        return self.terminal_api.get_terminal_snapshot(**kwargs)

    def trading_desk_dashboard(self, **kwargs):
        return self.trading_desk.dashboard(**kwargs)


_MODULE = None

def get_forex_module(db: Optional[Any] = None) -> ForexModule:
    global _MODULE
    if _MODULE is None or (db is not None and _MODULE.db is None):
        _MODULE = ForexModule(db=db)
    return _MODULE


def render_forex_module(db: Optional[Any] = None):
    return get_forex_module(db=db).render()
