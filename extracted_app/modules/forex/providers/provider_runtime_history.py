from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ProviderRuntimeStats:

    requests: int = 0

    successes: int = 0

    failures: int = 0

    total_latency_ms: float = 0.0

    @property
    def average_latency_ms(self) -> float:

        if self.successes == 0:
            return 0.0

        return self.total_latency_ms / self.successes

    @property
    def success_rate(self) -> float:

        if self.requests == 0:
            return 1.0

        return self.successes / self.requests


class ProviderRuntimeHistory:

    def __init__(self):

        self._providers: Dict[str, ProviderRuntimeStats] = {}

    def _stats(
        self,
        provider: str,
    ) -> ProviderRuntimeStats:

        if provider not in self._providers:
            self._providers[provider] = ProviderRuntimeStats()

        return self._providers[provider]

    def record_success(
        self,
        provider: str,
        latency_ms: float,
    ):

        stats = self._stats(provider)

        stats.requests += 1
        stats.successes += 1
        stats.total_latency_ms += latency_ms

    def record_failure(
        self,
        provider: str,
    ):

        stats = self._stats(provider)

        stats.requests += 1
        stats.failures += 1

    def get_stats(
        self,
        provider: str,
    ) -> ProviderRuntimeStats:

        return self._stats(provider)

    def snapshot(self):

        return self._providers


_RUNTIME_HISTORY = ProviderRuntimeHistory()


def get_provider_runtime_history():

    return _RUNTIME_HISTORY