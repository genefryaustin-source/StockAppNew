"""
modules/market_data/provider_router.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from threading import Lock
from typing import Dict, List, Optional


# ============================================================
# PROVIDER STATUS
# ============================================================

@dataclass
class ProviderStatus:

    provider: str

    enabled: bool = True

    health_score: float = 100.0

    success_count: int = 0
    failure_count: int = 0
    rate_limit_count: int = 0

    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None

    cooldown_until: Optional[datetime] = None

    avg_latency_ms: float = 0.0

    requests_today: int = 0


# ============================================================
# PROVIDER ROUTER
# ============================================================

class ProviderRouter:

    def __init__(self):

        self._lock = Lock()

        self.providers: Dict[str, ProviderStatus] = {}

        self._register_defaults()

    # ========================================================
    # REGISTRATION
    # ========================================================

    def _register_defaults(self):

        self.register_provider("POLYGON")
        self.register_provider("MARKETDATA")
        self.register_provider("ALPHA_VANTAGE")
        self.register_provider("YAHOO")
        self.register_provider("FINNHUB")
        self.register_provider("TWELVEDATA")

    def register_provider(
        self,
        provider_name: str,
    ):

        provider_name = provider_name.upper()

        self.providers[provider_name] = ProviderStatus(
            provider=provider_name
        )

    # ========================================================
    # LOOKUPS
    # ========================================================

    def get_provider(
        self,
        provider_name: str,
    ) -> Optional[ProviderStatus]:

        return self.providers.get(
            provider_name.upper()
        )

    def all_providers(self) -> List[ProviderStatus]:

        return list(
            self.providers.values()
        )

    # ========================================================
    # HEALTH
    # ========================================================

    def is_available(
        self,
        provider_name: str,
    ) -> bool:

        provider = self.get_provider(
            provider_name
        )

        if not provider:
            return False

        if not provider.enabled:
            return False

        if (
            provider.cooldown_until
            and provider.cooldown_until > datetime.now(UTC)
        ):
            return False

        return True

    def get_ranked_providers(self) -> List[ProviderStatus]:

        providers = []

        for provider in self.providers.values():

            if not self.is_available(
                provider.provider
            ):
                continue

            providers.append(provider)

        providers.sort(
            key=lambda p: p.health_score,
            reverse=True,
        )

        return providers

    # ========================================================
    # SUCCESS
    # ========================================================

    def mark_success(
        self,
        provider_name: str,
        latency_ms: float = 0,
    ):

        with self._lock:

            provider = self.get_provider(
                provider_name
            )

            if not provider:
                return

            provider.success_count += 1

            provider.last_success = datetime.now(
                UTC
            )

            provider.requests_today += 1

            if latency_ms > 0:

                if provider.avg_latency_ms <= 0:

                    provider.avg_latency_ms = latency_ms

                else:

                    provider.avg_latency_ms = (
                        provider.avg_latency_ms * 0.9
                        + latency_ms * 0.1
                    )

            provider.health_score = min(
                100,
                provider.health_score + 1,
            )

    # ========================================================
    # FAILURE
    # ========================================================

    def mark_failure(
        self,
        provider_name: str,
    ):

        with self._lock:

            provider = self.get_provider(
                provider_name
            )

            if not provider:
                return

            provider.failure_count += 1

            provider.last_failure = datetime.now(
                UTC
            )

            provider.health_score = max(
                0,
                provider.health_score - 5,
            )

    # ========================================================
    # RATE LIMIT
    # ========================================================

    def mark_rate_limited(
        self,
        provider_name: str,
        cooldown_minutes: int = 15,
    ):

        with self._lock:

            provider = self.get_provider(
                provider_name
            )

            if not provider:
                return

            provider.rate_limit_count += 1

            provider.last_failure = datetime.now(
                UTC
            )

            provider.cooldown_until = (
                datetime.now(UTC)
                + timedelta(
                    minutes=cooldown_minutes
                )
            )

            provider.health_score = max(
                0,
                provider.health_score - 25,
            )

    # ========================================================
    # ENABLE / DISABLE
    # ========================================================

    def disable_provider(
        self,
        provider_name: str,
    ):

        provider = self.get_provider(
            provider_name
        )

        if provider:
            provider.enabled = False

    def enable_provider(
        self,
        provider_name: str,
    ):

        provider = self.get_provider(
            provider_name
        )

        if provider:
            provider.enabled = True

    # ========================================================
    # RESET
    # ========================================================

    def reset_health(
        self,
        provider_name: str,
    ):

        provider = self.get_provider(
            provider_name
        )

        if not provider:
            return

        provider.health_score = 100

        provider.cooldown_until = None

        provider.failure_count = 0

        provider.rate_limit_count = 0

    # ========================================================
    # STATUS EXPORT
    # ========================================================

    def get_status_rows(self):

        rows = []

        for p in self.providers.values():

            rows.append(
                {
                    "provider": p.provider,
                    "enabled": p.enabled,
                    "health_score": p.health_score,
                    "success_count": p.success_count,
                    "failure_count": p.failure_count,
                    "rate_limit_count": p.rate_limit_count,
                    "avg_latency_ms": round(
                        p.avg_latency_ms,
                        2,
                    ),
                    "cooldown_until": p.cooldown_until,
                    "last_success": p.last_success,
                    "last_failure": p.last_failure,
                }
            )

        return rows


# ============================================================
# GLOBAL ROUTER
# ============================================================

_router: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:

    global _router

    if _router is None:

        _router = ProviderRouter()

    return _router