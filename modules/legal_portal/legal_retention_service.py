from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from .legal_retention import LegalRetentionRule, retention_cutoff


@dataclass(frozen=True)
class LegalRetentionCandidate:
    record_type: str
    record_id: str
    occurred_at: str
    cutoff_at: str
    eligible: bool
    legal_hold: bool
    reason: str


@dataclass(frozen=True)
class LegalRetentionPlan:
    generated_at: str
    candidates: tuple[LegalRetentionCandidate, ...]
    eligible_count: int
    held_count: int


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_retention_plan(
    *,
    records: Iterable[tuple[str, str, str, bool]],
    rule: LegalRetentionRule,
    now: datetime | None = None,
) -> LegalRetentionPlan:
    current = now or datetime.now(timezone.utc)
    cutoff = retention_cutoff(rule, now=current)

    candidates = []
    for record_type, record_id, occurred_at, legal_hold in records:
        occurred = _parse_datetime(occurred_at)
        eligible = occurred < cutoff and not legal_hold
        reason = (
            "legal hold"
            if legal_hold
            else "older than retention cutoff"
            if eligible
            else "within retention period"
        )
        candidates.append(
            LegalRetentionCandidate(
                record_type=record_type,
                record_id=record_id,
                occurred_at=occurred.isoformat(),
                cutoff_at=cutoff.isoformat(),
                eligible=eligible,
                legal_hold=legal_hold,
                reason=reason,
            )
        )

    return LegalRetentionPlan(
        generated_at=current.isoformat(),
        candidates=tuple(candidates),
        eligible_count=sum(item.eligible for item in candidates),
        held_count=sum(item.legal_hold for item in candidates),
    )
