from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable


class LegalRetentionClass(str, Enum):
    AGREEMENT = "agreement"
    REVIEW = "review"
    ACKNOWLEDGEMENT = "acknowledgement"
    AUDIT_EVENT = "audit_event"
    NOTIFICATION = "notification"
    OVERRIDE = "override"


@dataclass(frozen=True)
class LegalRetentionRule:
    retention_class: LegalRetentionClass
    retain_days: int
    description: str


DEFAULT_RETENTION_RULES = (
    LegalRetentionRule(
        LegalRetentionClass.AGREEMENT,
        3650,
        "Retain published and retired agreements for ten years.",
    ),
    LegalRetentionRule(
        LegalRetentionClass.REVIEW,
        2555,
        "Retain review records for seven years.",
    ),
    LegalRetentionRule(
        LegalRetentionClass.ACKNOWLEDGEMENT,
        2555,
        "Retain acknowledgement evidence for seven years.",
    ),
    LegalRetentionRule(
        LegalRetentionClass.AUDIT_EVENT,
        2555,
        "Retain workflow audit events for seven years.",
    ),
    LegalRetentionRule(
        LegalRetentionClass.NOTIFICATION,
        1095,
        "Retain notification delivery evidence for three years.",
    ),
    LegalRetentionRule(
        LegalRetentionClass.OVERRIDE,
        2555,
        "Retain override decisions for seven years.",
    ),
)


def retention_cutoff(
    rule: LegalRetentionRule,
    *,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(timezone.utc)
    return current - timedelta(days=rule.retain_days)
