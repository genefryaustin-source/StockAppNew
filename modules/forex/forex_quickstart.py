"""
modules/forex/forex_quickstart.py

Quick-start helpers for integrating the Forex SDK into StockApp.
"""

from __future__ import annotations

from modules.forex.forex_sdk import get_forex_sdk


def quickstart(db=None):
    sdk = get_forex_sdk(db=db)
    return {
        "initialize": sdk.initialize(),
        "health": sdk.health(),
        "status": sdk.status(),
    }


def trading_demo(pair="EURUSD", units=10000, db=None):
    sdk = get_forex_sdk(db=db)
    return {
        "quote": sdk.quotes(pair),
        "order": sdk.submit_order(
            pair=pair,
            side="BUY",
            units=units,
            order_type="MARKET",
        ),
        "portfolio": sdk.portfolio_summary(),
    }


def analytics_demo(db=None):
    sdk = get_forex_sdk(db=db)
    return {
        "strength": sdk.currency_strength(),
        "sentiment": sdk.sentiment(),
        "macro": sdk.macro_regime(),
        "alpha": sdk.alpha_model(),
        "strategy": sdk.strategy_lab(),
    }


def administration_demo(db=None):
    sdk = get_forex_sdk(db=db)
    return {
        "validation": sdk.validate(),
        "production": sdk.production_readiness(),
        "snapshot": sdk.enterprise_snapshot(),
    }
