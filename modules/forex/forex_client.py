"""
modules/forex/forex_client.py

Client facade used by external application components.
"""

from __future__ import annotations

from typing import Any, Dict

from modules.forex.forex_sdk import get_forex_sdk


class ForexClient:

    def __init__(self):
        self.sdk = get_forex_sdk()

    def connect(self) -> Dict[str, Any]:
        return self.sdk.initialize()

    def disconnect(self) -> Dict[str, Any]:
        return self.sdk.shutdown()

    def heartbeat(self) -> Dict[str, Any]:
        return {
            "status": "online",
            "dashboard": self.sdk.dashboard(),
        }

    def refresh(self):
        return self.sdk.refresh()

    def dashboard(self):
        return self.sdk.dashboard()

    def command_center(self):
        return self.sdk.command_center()

    def opportunities(self):
        return self.sdk.opportunities()

    def currency_strength(self):
        return self.sdk.strength()

    def macro_regime(self):
        return self.sdk.macro()

    def carry_trades(self):
        return self.sdk.carry()

    def institutional_flow(self):
        return self.sdk.institutional()

    def central_banks(self):
        return self.sdk.central_banks()

    def sentiment(self):
        return self.sdk.sentiment()

    def portfolio(self):
        return self.sdk.portfolio()

    def render(self):
        self.sdk.render()


_CLIENT=None

def get_forex_client():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT=ForexClient()
    return _CLIENT
