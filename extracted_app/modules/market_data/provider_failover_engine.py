"""
modules/market_data/provider_failover_engine.py
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Optional

from modules.market_data.provider_router import (
    get_provider_router,
)


class ProviderFailoverEngine:

    def __init__(self):
        self.router = get_provider_router()

    def select_provider(
        self,
        allowed_providers=None,
    ):

        ranked = self.router.get_ranked_providers(
            allowed=allowed_providers,
        )

        if not ranked:
            return None

        return ranked[0]

    def get_failover_chain(
        self,
        allowed_providers=None,
    ):

        ranked = self.router.get_ranked_providers(
            allowed=allowed_providers,
        )

        return [
            p.provider
            for p in ranked
        ]

    def mark_success(
        self,
        provider_name: str,
        latency_ms: float = 0,
    ):
        self.router.mark_success(
            provider_name,
            latency_ms=latency_ms,
        )

    def mark_failure(
        self,
        provider_name: str,
    ):
        self.router.mark_failure(
            provider_name,
        )

    def mark_rate_limited(
        self,
        provider_name: str,
        cooldown_minutes: int = 15,
    ):
        self.router.mark_rate_limited(
            provider_name,
            cooldown_minutes=cooldown_minutes,
        )

    def provider_available(
        self,
        provider_name: str,
    ) -> bool:
        return self.router.is_available(
            provider_name,
        )


_engine: Optional[
    ProviderFailoverEngine
] = None


def get_provider_failover_engine():

    global _engine

    if _engine is None:
        _engine = ProviderFailoverEngine()

    return _engine