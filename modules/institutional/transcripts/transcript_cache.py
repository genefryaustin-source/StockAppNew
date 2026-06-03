"""
modules/institutional/transcripts/transcript_cache.py

Database-backed transcript cache using the existing EarningsEvent ORM model.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from modules.institutional.models import EarningsEvent
from .transcript_provider import TranscriptProviderResult
from .transcript_normalizer import clean_transcript_text, parse_event_date


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_event_datetime(value: Optional[str]) -> datetime:
    if not value:
        return utc_now()

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return utc_now()


class TranscriptCache:
    def __init__(self, *, min_cached_chars: int = 1000) -> None:
        self.min_cached_chars = min_cached_chars

    def get_latest_event(
        self,
        db: Session,
        tenant_id: str,
        symbol: str,
    ) -> Optional[EarningsEvent]:
        sym = str(symbol or "").upper().strip()
        if not sym:
            return None

        return (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == sym,
                EarningsEvent.transcript_text != None,
            )
            .order_by(EarningsEvent.event_date.desc())
            .first()
        )

    def get_latest_transcript(
        self,
        db: Session,
        tenant_id: str,
        symbol: str,
    ) -> Optional[str]:
        event = self.get_latest_event(db, tenant_id, symbol)

        if not event or not getattr(event, "transcript_text", None):
            return None

        transcript = clean_transcript_text(event.transcript_text)

        if len(transcript) < self.min_cached_chars:
            return None

        return transcript

    def store_result(
        self,
        db: Session,
        tenant_id: str,
        result: TranscriptProviderResult,
    ) -> Tuple[bool, str, Optional[EarningsEvent]]:
        transcript = clean_transcript_text(result.transcript_text)

        if len(transcript) < self.min_cached_chars:
            return False, "Transcript was too short to cache.", None

        event_dt = _parse_event_datetime(result.event_date)
        sym = result.symbol.upper().strip()

        event = (
            db.query(EarningsEvent)
            .filter(
                EarningsEvent.tenant_id == tenant_id,
                EarningsEvent.symbol == sym,
                EarningsEvent.event_date == event_dt,
            )
            .first()
        )

        if not event:
            event = EarningsEvent(
                tenant_id=tenant_id,
                symbol=sym,
                event_date=event_dt,
            )
            db.add(event)

        event.transcript_text = transcript
        event.transcript_url = result.source_url
        event.transcript_fetched_at = utc_now()
        event.transcript_source = result.provider_name
        event.transcript_chunks_indexed = False

        db.commit()

        return True, f"Transcript cached for {sym} from {result.provider_name}.", event

    def store_manual(
        self,
        db: Session,
        tenant_id: str,
        symbol: str,
        transcript_text: str,
        *,
        event_date: Optional[datetime] = None,
        transcript_url: Optional[str] = None,
        source: str = "manual",
    ) -> Tuple[bool, str, Optional[EarningsEvent]]:
        transcript = clean_transcript_text(transcript_text)
        if len(transcript) < self.min_cached_chars:
            return False, f"Transcript must be at least {self.min_cached_chars} characters.", None

        result = TranscriptProviderResult(
            symbol=symbol.upper().strip(),
            transcript_text=transcript,
            provider_name=source,
            source_url=transcript_url,
            event_date=(event_date or utc_now()).astimezone(timezone.utc).isoformat(),
        )

        return self.store_result(db, tenant_id, result)
