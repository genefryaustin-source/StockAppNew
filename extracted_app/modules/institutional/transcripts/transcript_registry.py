"""
modules/institutional/transcripts/transcript_registry.py

Provider registry with ordered failover.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .transcript_provider import TranscriptProvider, TranscriptProviderResult


@dataclass
class TranscriptRegistryResult:
    result: Optional[TranscriptProviderResult]
    provider_attempts: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.as_dict() if self.result else None,
            "provider_attempts": self.provider_attempts,
        }


class TranscriptRegistry:
    def __init__(self) -> None:
        self.providers: List[TranscriptProvider] = []

    def register(self, provider: TranscriptProvider) -> TranscriptProvider:
        self.providers.append(provider)
        self.providers.sort(key=lambda p: p.priority)
        return provider

    def unregister(self, provider_name: str) -> bool:
        before = len(self.providers)
        self.providers = [p for p in self.providers if p.provider_name != provider_name]
        return len(self.providers) < before

    def provider_inventory(self) -> List[Dict[str, Any]]:
        return [
            {
                "provider_name": provider.provider_name,
                "display_name": provider.display_name,
                "priority": provider.priority,
                "enabled": provider.enabled,
                "status": provider.status,
                "health": provider.health_status(),
            }
            for provider in self.providers
        ]

    def fetch_latest(self, symbol: str) -> TranscriptRegistryResult:
        attempts: List[Dict[str, Any]] = []

        for provider in self.providers:
            if not provider.can_fetch():
                attempts.append(
                    {
                        "provider": provider.provider_name,
                        "status": "SKIPPED",
                        "reason": "Provider disabled or unavailable.",
                    }
                )
                continue

            provider.mark_attempt()

            try:
                result = provider.fetch_latest_transcript(symbol)
                result = provider._validate_result(result)

                if result:
                    provider.mark_success()
                    attempts.append(
                        {
                            "provider": provider.provider_name,
                            "status": "SUCCESS",
                            "transcript_chars": len(result.transcript_text or ""),
                        }
                    )
                    return TranscriptRegistryResult(result=result, provider_attempts=attempts)

                attempts.append(
                    {
                        "provider": provider.provider_name,
                        "status": "NO_RESULT",
                    }
                )

            except Exception as exc:
                provider.mark_failure(exc)
                attempts.append(
                    {
                        "provider": provider.provider_name,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

        return TranscriptRegistryResult(result=None, provider_attempts=attempts)


def build_default_transcript_registry() -> TranscriptRegistry:
    from .providers.manual_provider import ManualTranscriptProvider
    from .providers.roic_provider import ROICProvider
    from .providers.quartr_provider import QuartrProvider
    from .providers.fmp_legacy_provider import FMPLegacyProvider

    registry = TranscriptRegistry()

    # Manual does not fetch, but is represented for inventory/diagnostics.
    registry.register(ManualTranscriptProvider(enabled=True, priority=1000))

    # API providers. Disabled automatically when no key exists.
    registry.register(ROICProvider(priority=10))
    registry.register(QuartrProvider(priority=20))
    registry.register(FMPLegacyProvider(priority=900))

    return registry
