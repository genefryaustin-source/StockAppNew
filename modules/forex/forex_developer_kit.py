"""
modules/forex/forex_developer_kit.py

Developer utilities for integrating and testing the Forex SDK.
"""

from __future__ import annotations

from modules.forex.forex_sdk import get_forex_sdk


class ForexDeveloperKit:
    def __init__(self, db=None):
        self.db=db
        self.sdk=get_forex_sdk(db=db)

    def smoke_test(self):
        return {
            "health": self.sdk.health(),
            "status": self.sdk.status(),
        }

    def integration_check(self):
        return {
            "metadata": self.sdk.platform_metadata(),
            "snapshot": self.sdk.enterprise_snapshot(),
        }

    def trading_sample(self, pair="EURUSD"):
        return {
            "quote": self.sdk.quotes(pair),
            "portfolio": self.sdk.portfolio_summary(),
        }

    def api_catalog(self):
        return {
            "lifecycle":["initialize","shutdown","reload","status","health"],
            "trading":["submit_order","cancel_order","close_position"],
            "analytics":["strategy_lab","alpha_model","performance"],
            "admin":["validate","benchmark","stress_test","production_readiness"],
        }


_DEVKIT=None

def get_forex_developer_kit(db=None):
    global _DEVKIT
    if _DEVKIT is None or (db is not None and _DEVKIT.db is None):
        _DEVKIT=ForexDeveloperKit(db=db)
    return _DEVKIT
