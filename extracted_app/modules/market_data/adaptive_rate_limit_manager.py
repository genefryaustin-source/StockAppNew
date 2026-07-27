"""
modules/market_data/adaptive_rate_limit_manager.py
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from threading import Lock
from typing import Dict, Optional


@dataclass
class RateLimitState:
    provider: str
    min_delay_seconds: float = 0.25
    current_delay_seconds: float = 0.25
    cooldown_until: Optional[datetime] = None
    rate_limit_count: int = 0
    last_rate_limit: Optional[datetime] = None
    last_request: Optional[datetime] = None


class AdaptiveRateLimitManager:
    def __init__(self):
        self._lock = Lock()
        self._states: Dict[str, RateLimitState] = {}

        self.register("POLYGON", min_delay_seconds=0.50)
        self.register("MARKETDATA", min_delay_seconds=0.75)
        self.register("ALPHA_VANTAGE", min_delay_seconds=12.0)
        self.register("FINNHUB", min_delay_seconds=2.0)
        self.register("TWELVEDATA", min_delay_seconds=3.0)
        self.register("YAHOO", min_delay_seconds=1.5)

    def register(self, provider: str, min_delay_seconds: float = 1.0):
        provider = provider.upper()
        self._states[provider] = RateLimitState(
            provider=provider,
            min_delay_seconds=min_delay_seconds,
            current_delay_seconds=min_delay_seconds,
        )

    def get_state(self, provider: str) -> RateLimitState:
        provider = provider.upper()
        if provider not in self._states:
            self.register(provider)
        return self._states[provider]

    def is_available(self, provider: str) -> bool:
        state = self.get_state(provider)
        if state.cooldown_until and state.cooldown_until > datetime.now(UTC):
            return False
        return True

    def wait_if_needed(self, provider: str):
        provider = provider.upper()
        state = self.get_state(provider)

        if not self.is_available(provider):
            sleep_for = max(
                0.0,
                (state.cooldown_until - datetime.now(UTC)).total_seconds(),
            )
            if sleep_for > 0:
                time.sleep(min(sleep_for, 60.0))

        with self._lock:
            now = datetime.now(UTC)

            if state.last_request:
                elapsed = (now - state.last_request).total_seconds()
                remaining = state.current_delay_seconds - elapsed

                if remaining > 0:
                    time.sleep(remaining)

            state.last_request = datetime.now(UTC)

    def mark_success(self, provider: str):
        state = self.get_state(provider)
        state.current_delay_seconds = max(
            state.min_delay_seconds,
            state.current_delay_seconds * 0.90,
        )

    def mark_rate_limited(
        self,
        provider: str,
        cooldown_minutes: int = 15,
    ):
        state = self.get_state(provider)
        state.rate_limit_count += 1
        state.last_rate_limit = datetime.now(UTC)
        state.cooldown_until = datetime.now(UTC) + timedelta(
            minutes=cooldown_minutes
        )
        state.current_delay_seconds = min(
            60.0,
            max(state.current_delay_seconds * 2.0, state.min_delay_seconds),
        )

    def mark_failure(self, provider: str):
        state = self.get_state(provider)
        state.current_delay_seconds = min(
            30.0,
            max(state.current_delay_seconds * 1.25, state.min_delay_seconds),
        )

    def rows(self):
        return [
            {
                "provider": s.provider,
                "min_delay_seconds": s.min_delay_seconds,
                "current_delay_seconds": round(s.current_delay_seconds, 2),
                "cooldown_until": s.cooldown_until,
                "rate_limit_count": s.rate_limit_count,
                "last_rate_limit": s.last_rate_limit,
                "last_request": s.last_request,
            }
            for s in self._states.values()
        ]


_rate_manager: Optional[AdaptiveRateLimitManager] = None


def get_rate_limit_manager() -> AdaptiveRateLimitManager:
    global _rate_manager

    if _rate_manager is None:
        _rate_manager = AdaptiveRateLimitManager()

    return _rate_manager