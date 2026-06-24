"""
modules/market_data/provider_router.py
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from threading import Lock
from typing import Dict, List, Optional

from modules.market_data.adaptive_rate_limit_manager import (
    get_rate_limit_manager,
)


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


class ProviderRouter:
    def __init__(self):
        self._lock = Lock()
        self.providers: Dict[str, ProviderStatus] = {}
        self.rate_manager = get_rate_limit_manager()
        self._register_defaults()

    def _register_defaults(self):
        self.register_provider("POLYGON")
        self.register_provider("MARKETDATA")
        self.register_provider("ALPHA_VANTAGE")
        self.register_provider("FINNHUB")
        self.register_provider("TWELVEDATA")

    def register_provider(self, provider_name: str):
        provider_name = str(provider_name).upper().strip()
        if provider_name not in self.providers:
            self.providers[provider_name] = ProviderStatus(provider=provider_name)

    def get_provider(self, provider_name: str) -> Optional[ProviderStatus]:
        return self.providers.get(str(provider_name).upper().strip())

    def all_providers(self) -> List[ProviderStatus]:
        return list(self.providers.values())

    def is_available(self, provider_name: str) -> bool:
        provider = self.get_provider(provider_name)

        if not provider:
            return False

        if not provider.enabled:
            return False

        if provider.cooldown_until and provider.cooldown_until > datetime.now(UTC):
            return False

        if not self.rate_manager.is_available(provider.provider):
            return False

        return True

    def wait_for_provider(self, provider_name: str):
        self.rate_manager.wait_if_needed(provider_name)

    def get_ranked_providers(
        self,
        allowed: Optional[List[str]] = None,
    ) -> List[ProviderStatus]:
        allowed_set = None

        if allowed:
            allowed_set = {str(p).upper().strip() for p in allowed}

        providers = []

        for provider in self.providers.values():
            if allowed_set and provider.provider not in allowed_set:
                continue

            if not self.is_available(provider.provider):
                continue

            providers.append(provider)

        providers.sort(
            key=lambda p: p.health_score,
            reverse=True,
        )

        return providers

    def mark_success(
        self,
        provider_name: str,
        latency_ms: float = 0,
    ):
        with self._lock:
            provider = self.get_provider(provider_name)

            if not provider:
                return

            provider.success_count += 1
            provider.last_success = datetime.now(UTC)
            provider.requests_today += 1

            if latency_ms > 0:
                if provider.avg_latency_ms <= 0:
                    provider.avg_latency_ms = latency_ms
                else:
                    provider.avg_latency_ms = (
                        provider.avg_latency_ms * 0.90
                        + latency_ms * 0.10
                    )

            provider.health_score = min(
                100.0,
                provider.health_score + 1.0,
            )

            self.rate_manager.mark_success(provider.provider)

    def mark_failure(self, provider_name: str):
        with self._lock:
            provider = self.get_provider(provider_name)

            if not provider:
                return

            provider.failure_count += 1
            provider.last_failure = datetime.now(UTC)

            provider.health_score = max(
                0.0,
                provider.health_score - 5.0,
            )

            self.rate_manager.mark_failure(provider.provider)

    def mark_rate_limited(
        self,
        provider_name: str,
        cooldown_minutes: int = 15,
    ):
        with self._lock:
            provider = self.get_provider(provider_name)

            if not provider:
                return

            provider.rate_limit_count += 1
            provider.last_failure = datetime.now(UTC)
            provider.cooldown_until = datetime.now(UTC) + timedelta(
                minutes=cooldown_minutes
            )

            provider.health_score = max(
                0.0,
                provider.health_score - 25.0,
            )

            self.rate_manager.mark_rate_limited(
                provider.provider,
                cooldown_minutes=cooldown_minutes,
            )

    def disable_provider(self, provider_name: str):
        provider = self.get_provider(provider_name)
        if provider:
            provider.enabled = False

    def enable_provider(self, provider_name: str):
        provider = self.get_provider(provider_name)
        if provider:
            provider.enabled = True

    def reset_health(self, provider_name: str):
        provider = self.get_provider(provider_name)

        if not provider:
            return

        provider.health_score = 100.0
        provider.cooldown_until = None
        provider.failure_count = 0
        provider.rate_limit_count = 0

    def get_status_rows(self):
        rows = []

        for p in self.providers.values():
            rows.append(
                {
                    "provider": p.provider,
                    "enabled": p.enabled,
                    "health_score": round(p.health_score, 2),
                    "success_count": p.success_count,
                    "failure_count": p.failure_count,
                    "rate_limit_count": p.rate_limit_count,
                    "avg_latency_ms": round(p.avg_latency_ms, 2),
                    "cooldown_until": p.cooldown_until,
                    "last_success": p.last_success,
                    "last_failure": p.last_failure,
                }
            )

        return rows

    def get_provider_snapshot(self):
        return [
            {
                "provider": p.provider,
                "enabled": p.enabled,
                "health_score": p.health_score,
                "success_count": p.success_count,
                "failure_count": p.failure_count,
                "rate_limit_count": p.rate_limit_count,
                "avg_latency_ms": p.avg_latency_ms,
                "cooldown_until": p.cooldown_until,
                "last_success": p.last_success,
                "last_failure": p.last_failure,
            }
            for p in self.providers.values()
        ]


_router: Optional[ProviderRouter] = None


def get_provider_router() -> ProviderRouter:
    global _router

    if _router is None:
        _router = ProviderRouter()

    return _router


def is_rate_limit_error(error: Exception | str) -> bool:
    msg = str(error).lower()

    markers = [
        "429",
        "rate limit",
        "rate-limited",
        "too many requests",
        "maximum requests per minute",
        "api limit reached",
        "remaining limit: 0",
        "quota",
    ]

    return any(m in msg for m in markers)