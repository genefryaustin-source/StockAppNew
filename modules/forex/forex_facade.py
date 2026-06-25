"""
modules/forex/forex_facade.py

Single-entry facade for the Forex subsystem.
"""

from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_gateway import get_forex_gateway


class ForexFacade:
    """Highest-level interface for application consumers."""

    def __init__(self):
        self.gateway = get_forex_gateway()

    def initialize(self) -> Dict[str, Any]:
        return self.gateway.initialize()

    def shutdown(self) -> Dict[str, Any]:
        return self.gateway.shutdown()

    def refresh(self):
        return self.gateway.refresh()

    def health(self):
        return self.gateway.health()

    def overview(self):
        return self.gateway.overview()

    def analytics(self):
        return self.gateway.analytics()

    def render(self):
        self.gateway.render()


_FACADE = None

def get_forex_facade():
    global _FACADE
    if _FACADE is None:
        _FACADE = ForexFacade()
    return _FACADE


def run_forex():
    get_forex_facade().render()
