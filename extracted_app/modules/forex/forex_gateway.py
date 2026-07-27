"""
modules/forex/forex_gateway.py

Canonical gateway for the Forex subsystem.
"""

from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_client import get_forex_client


class ForexGateway:
    """Stable integration layer for the rest of StockApp."""

    def __init__(self):
        self.client = get_forex_client()

    def initialize(self) -> Dict[str, Any]:
        return self.client.connect()

    def shutdown(self) -> Dict[str, Any]:
        return self.client.disconnect()

    def health(self) -> Dict[str, Any]:
        return self.client.heartbeat()

    def refresh(self):
        return self.client.refresh()

    def overview(self):
        return self.client.dashboard()

    def analytics(self):
        return {
            "command_center": self.client.command_center(),
            "opportunities": self.client.opportunities(),
            "currency_strength": self.client.currency_strength(),
            "macro_regime": self.client.macro_regime(),
            "carry_trades": self.client.carry_trades(),
            "institutional_flow": self.client.institutional_flow(),
            "central_banks": self.client.central_banks(),
            "sentiment": self.client.sentiment(),
            "portfolio": self.client.portfolio(),
        }

    def render(self):
        self.client.render()


_GATEWAY=None

def get_forex_gateway():
    global _GATEWAY
    if _GATEWAY is None:
        _GATEWAY=ForexGateway()
    return _GATEWAY


def launch_forex_gateway():
    get_forex_gateway().render()
