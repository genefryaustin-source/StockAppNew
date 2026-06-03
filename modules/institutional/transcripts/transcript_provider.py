"""
modules/institutional/transcripts/transcript_provider.py

Provider base types for earnings-call transcript retrieval.

Design goals:
- Providers are isolated from UI and database code.
- Providers return normalized TranscriptProviderResult objects.
- Provider errors are structured and safe to show in diagnostics.
- Providers can be enabled/disabled without breaking the service.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TranscriptProviderStatus(str, Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"


class TranscriptProviderError(Exception):
    """Provider-level exception with a user-safe message."""

    def __init__(
        self,
        message: str,
        *,
        provider_name: str = "",
        status_code: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.provider_name = provider_name
        self.status_code = status_code
        self.payload = payload or {}

    def as_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "message": str(self),
            "status_code": self.status_code,
            "payload": self.payload,
        }


@dataclass
class TranscriptProviderResult:
    symbol: str
    transcript_text: str
    provider_name: str
    source_url: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    event_date: Optional[str] = None
    title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=utc_now_iso)

    def is_valid(self, min_chars: int = 1000) -> bool:
        return bool(self.transcript_text and len(self.transcript_text.strip()) >= min_chars)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptProviderHealth:
    provider_name: str
    status: str
    enabled: bool
    priority: int
    requests_attempted: int = 0
    requests_succeeded: int = 0
    requests_failed: int = 0
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_error: Optional[str] = None
    updated_at: str = field(default_factory=utc_now_iso)

    def success_rate(self) -> float:
        if self.requests_attempted <= 0:
            return 1.0
        return round(self.requests_succeeded / self.requests_attempted, 4)

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["success_rate"] = self.success_rate()
        return data


class TranscriptProvider(ABC):
    provider_name: str = "base"
    display_name: str = "Base Provider"

    def __init__(
        self,
        *,
        enabled: bool = True,
        priority: int = 100,
        timeout_seconds: int = 30,
        min_transcript_chars: int = 1000,
    ) -> None:
        self.enabled = enabled
        self.priority = priority
        self.timeout_seconds = timeout_seconds
        self.min_transcript_chars = min_transcript_chars
        self.status = TranscriptProviderStatus.ENABLED.value if enabled else TranscriptProviderStatus.DISABLED.value
        self.health = TranscriptProviderHealth(
            provider_name=self.provider_name,
            status=self.status,
            enabled=self.enabled,
            priority=self.priority,
        )

    @abstractmethod
    def fetch_latest_transcript(self, symbol: str) -> Optional[TranscriptProviderResult]:
        """Return latest transcript for symbol, or None when unavailable."""
        raise NotImplementedError

    def can_fetch(self) -> bool:
        return self.enabled and self.status != TranscriptProviderStatus.DISABLED.value

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        self.status = TranscriptProviderStatus.ENABLED.value if enabled else TranscriptProviderStatus.DISABLED.value
        self.health.enabled = self.enabled
        self.health.status = self.status
        self.health.updated_at = utc_now_iso()

    def mark_attempt(self) -> None:
        self.health.requests_attempted += 1
        self.health.updated_at = utc_now_iso()

    def mark_success(self) -> None:
        self.status = TranscriptProviderStatus.ENABLED.value
        self.health.status = self.status
        self.health.requests_succeeded += 1
        self.health.last_success_at = utc_now_iso()
        self.health.last_error = None
        self.health.updated_at = utc_now_iso()

    def mark_failure(self, error: Exception) -> None:
        self.status = TranscriptProviderStatus.DEGRADED.value if self.enabled else TranscriptProviderStatus.DISABLED.value
        self.health.status = self.status
        self.health.requests_failed += 1
        self.health.last_failure_at = utc_now_iso()
        self.health.last_error = str(error)
        self.health.updated_at = utc_now_iso()

    def health_status(self) -> Dict[str, Any]:
        return self.health.as_dict()

    def _normalize_symbol(self, symbol: str) -> str:
        return str(symbol or "").strip().upper()

    def _validate_result(self, result: Optional[TranscriptProviderResult]) -> Optional[TranscriptProviderResult]:
        if not result:
            return None

        if not result.is_valid(self.min_transcript_chars):
            raise TranscriptProviderError(
                f"Transcript from {self.display_name} is too short or empty.",
                provider_name=self.provider_name,
                payload={
                    "length": len(result.transcript_text or ""),
                    "min_transcript_chars": self.min_transcript_chars,
                },
            )

        return result
