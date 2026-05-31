"""
modules/market_data/provider_strategy_engine.py
"""

from __future__ import annotations

from typing import Dict, List, Optional

from modules.market_data.provider_learning_engine import (
    get_provider_learning_engine,
)


REQUEST_PRICE_HISTORY = "PRICE_HISTORY"
REQUEST_LATEST_PRICE = "LATEST_PRICE"
REQUEST_FUNDAMENTALS = "FUNDAMENTALS"
REQUEST_PROFILE = "PROFILE"
REQUEST_NEWS = "NEWS"
REQUEST_OPTIONS = "OPTIONS"


DEFAULT_STRATEGIES: Dict[str, List[str]] = {
    REQUEST_PRICE_HISTORY: [
        "POLYGON",
        "MARKETDATA",
        "ALPHA_VANTAGE",
        "YAHOO",
    ],
    REQUEST_LATEST_PRICE: [
        "FINNHUB",
        "POLYGON",
        "YAHOO",
    ],
    REQUEST_FUNDAMENTALS: [
        "FINNHUB",
        "FMP",
        "POLYGON",
    ],
    REQUEST_PROFILE: [
        "FINNHUB",
        "FMP",
        "POLYGON",
    ],
    REQUEST_NEWS: [
        "FINNHUB",
        "NEWSAPI",
    ],
    REQUEST_OPTIONS: [
        "MARKETDATA",
        "POLYGON",
    ],
}


class ProviderStrategyEngine:
    def __init__(self):
        self.learning = get_provider_learning_engine()

    def get_allowed_providers(
        self,
        request_type: str,
        db=None,
    ) -> List[str]:
        request_type = request_type.upper()

        base = DEFAULT_STRATEGIES.get(
            request_type,
            [
                "POLYGON",
                "MARKETDATA",
                "ALPHA_VANTAGE",
                "YAHOO",
                "FINNHUB",
            ],
        )
        print(
            "STRATEGY PROVIDERS:",
            base
        )
        if db is None:
            return base

        learned_best: Optional[str] = (
            self.learning.best_provider_for_request(
                db,
                request_type,
            )
        )

        if learned_best and learned_best in base:
            return [
                learned_best,
                *[
                    p for p in base
                    if p != learned_best
                ],
            ]

        return base

    def describe_strategy(
        self,
        request_type: str,
        db=None,
    ):
        providers = self.get_allowed_providers(
            request_type,
            db=db,
        )

        return {
            "request_type": request_type.upper(),
            "providers": providers,
            "primary": providers[0] if providers else None,
            "fallbacks": providers[1:],
        }


_strategy_engine = None


def get_provider_strategy_engine():
    global _strategy_engine

    if _strategy_engine is None:
        _strategy_engine = ProviderStrategyEngine()

    return _strategy_engine