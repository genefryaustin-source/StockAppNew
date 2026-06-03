"""
modules/institutional/transcripts/transcript_service.py

High-level transcript service. The UI should call this instead of provider code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from .transcript_cache import TranscriptCache
from .transcript_registry import TranscriptRegistry, build_default_transcript_registry
from .transcript_normalizer import clean_transcript_text, transcript_preview


@dataclass
class TranscriptServiceResult:
    symbol: str
    transcript_text: Optional[str]
    source: str
    cached: bool
    success: bool
    message: str
    event_date: Optional[str] = None
    source_url: Optional[str] = None
    provider_attempts: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["transcript_chars"] = len(self.transcript_text or "")
        data["preview"] = transcript_preview(self.transcript_text or "", 600)
        return data


class TranscriptService:
    def __init__(
        self,
        *,
        registry: Optional[TranscriptRegistry] = None,
        cache: Optional[TranscriptCache] = None,
    ) -> None:
        self.registry = registry or build_default_transcript_registry()
        self.cache = cache or TranscriptCache()

    def get_or_fetch_latest(
        self,
        db: Session,
        tenant_id: str,
        symbol: str,
        *,
        force_refresh: bool = False,
    ) -> TranscriptServiceResult:
        sym = str(symbol or "").upper().strip()

        if not sym:
            return TranscriptServiceResult(
                symbol=sym,
                transcript_text=None,
                source="none",
                cached=False,
                success=False,
                message="Symbol is required.",
            )

        if not force_refresh:
            cached = self.cache.get_latest_transcript(db, tenant_id, sym)
            if cached:
                event = self.cache.get_latest_event(db, tenant_id, sym)
                return TranscriptServiceResult(
                    symbol=sym,
                    transcript_text=cached,
                    source=getattr(event, "transcript_source", "cache") or "cache",
                    cached=True,
                    success=True,
                    message=f"Loaded cached transcript for {sym}.",
                    event_date=getattr(event, "event_date", None).isoformat() if getattr(event, "event_date", None) else None,
                    source_url=getattr(event, "transcript_url", None),
                )

        registry_result = self.registry.fetch_latest(sym)

        if registry_result.result:
            ok, message, event = self.cache.store_result(db, tenant_id, registry_result.result)
            if not ok:
                return TranscriptServiceResult(
                    symbol=sym,
                    transcript_text=registry_result.result.transcript_text,
                    source=registry_result.result.provider_name,
                    cached=False,
                    success=False,
                    message=message,
                    provider_attempts=registry_result.provider_attempts,
                )

            return TranscriptServiceResult(
                symbol=sym,
                transcript_text=registry_result.result.transcript_text,
                source=registry_result.result.provider_name,
                cached=False,
                success=True,
                message=message,
                event_date=getattr(event, "event_date", None).isoformat() if getattr(event, "event_date", None) else registry_result.result.event_date,
                source_url=registry_result.result.source_url,
                provider_attempts=registry_result.provider_attempts,
            )

        return TranscriptServiceResult(
            symbol=sym,
            transcript_text=None,
            source="none",
            cached=False,
            success=False,
            message=(
                f"No transcript provider returned a transcript for {sym}. "
                "Use manual upload or configure a supported transcript API key."
            ),
            provider_attempts=registry_result.provider_attempts,
        )

    def store_manual_transcript(
        self,
        db: Session,
        tenant_id: str,
        symbol: str,
        transcript_text: str,
        *,
        event_date: Optional[datetime] = None,
        transcript_url: Optional[str] = None,
        source: str = "manual",
    ) -> TranscriptServiceResult:
        ok, message, event = self.cache.store_manual(
            db,
            tenant_id,
            symbol,
            transcript_text,
            event_date=event_date,
            transcript_url=transcript_url,
            source=source,
        )

        transcript = clean_transcript_text(transcript_text) if ok else None

        return TranscriptServiceResult(
            symbol=str(symbol or "").upper().strip(),
            transcript_text=transcript,
            source=source,
            cached=False,
            success=ok,
            message=message,
            event_date=getattr(event, "event_date", None).isoformat() if event else None,
            source_url=transcript_url,
        )

    def provider_status(self) -> list[dict[str, Any]]:
        return self.registry.provider_inventory()


def build_transcript_service() -> TranscriptService:
    return TranscriptService()
