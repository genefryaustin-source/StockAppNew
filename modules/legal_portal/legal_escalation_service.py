from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional

from .legal_compliance_service import is_overdue
from .legal_escalation_models import LegalEscalationLevel
from .legal_notifications import (
    LegalNotification,
    LegalNotificationType,
    NotificationSink,
    send_notification,
)
from .legal_registry import DOCUMENTS
from .legal_workflow_models import LegalAcknowledgement
from .legal_workflow_service import LegalWorkflowService


@dataclass(frozen=True)
class LegalEscalationPolicy:
    reminder_after_days: int = 0
    manager_after_days: int = 3
    tenant_admin_after_days: int = 7
    super_admin_after_days: int = 14
    repeat_interval_days: int = 3


DEFAULT_ESCALATION_POLICY = LegalEscalationPolicy()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def days_overdue(
    acknowledgement: LegalAcknowledgement,
    *,
    now: datetime | None = None,
) -> int:
    due = _parse_datetime(acknowledgement.due_at)

    if due is None:
        return 0

    current = now or datetime.now(timezone.utc)

    if due >= current:
        return 0

    return max(0, (current - due).days)


def escalation_level(
    acknowledgement: LegalAcknowledgement,
    *,
    policy: LegalEscalationPolicy = DEFAULT_ESCALATION_POLICY,
    now: datetime | None = None,
) -> LegalEscalationLevel | None:
    if not is_overdue(acknowledgement, now=now):
        return None

    overdue_days = days_overdue(acknowledgement, now=now)

    if overdue_days >= policy.super_admin_after_days:
        return LegalEscalationLevel.SUPER_ADMIN
    if overdue_days >= policy.tenant_admin_after_days:
        return LegalEscalationLevel.TENANT_ADMIN
    if overdue_days >= policy.manager_after_days:
        return LegalEscalationLevel.MANAGER

    return LegalEscalationLevel.REMINDER


def notification_key(
    *,
    acknowledgement_id: str,
    level: LegalEscalationLevel,
    window_start: str,
) -> str:
    raw = f"{acknowledgement_id}|{level.value}|{window_start}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_escalation_notification(
    acknowledgement: LegalAcknowledgement,
    *,
    level: LegalEscalationLevel,
    recipient_user_id: str,
    recipient_email: str | None,
) -> LegalNotification:
    document = DOCUMENTS.get(acknowledgement.document_key)
    title = document.title if document else acknowledgement.document_key

    return LegalNotification(
        notification_type=LegalNotificationType.ACKNOWLEDGEMENT_OVERDUE,
        recipient_user_id=recipient_user_id,
        recipient_email=recipient_email,
        subject=f"Legal acknowledgement escalation: {title}",
        message=(
            f"{title}, version {acknowledgement.document_version}, "
            f"remains overdue for user {acknowledgement.user_id}. "
            f"Escalation level: {level.value.replace('_', ' ').title()}."
        ),
        document_key=acknowledgement.document_key,
        document_version=acknowledgement.document_version,
        acknowledgement_id=acknowledgement.id,
        tenant_id=acknowledgement.tenant_id,
    )


def run_escalations(
    *,
    service: LegalWorkflowService,
    recipient_resolver: Callable[
        [LegalAcknowledgement, LegalEscalationLevel],
        tuple[str, str | None] | None,
    ],
    notification_sink: NotificationSink | None = None,
    policy: LegalEscalationPolicy = DEFAULT_ESCALATION_POLICY,
    sent_key_exists: Callable[[str], bool] | None = None,
    record_sent_key: Callable[[str], None] | None = None,
    now: datetime | None = None,
) -> int:
    current = now or datetime.now(timezone.utc)
    sent = 0

    for acknowledgement in service.repository.list_acknowledgements():
        level = escalation_level(
            acknowledgement,
            policy=policy,
            now=current,
        )
        if level is None:
            continue

        recipient = recipient_resolver(acknowledgement, level)
        if recipient is None:
            continue

        recipient_user_id, recipient_email = recipient
        window = current.date().isoformat()
        key = notification_key(
            acknowledgement_id=acknowledgement.id,
            level=level,
            window_start=window,
        )

        if sent_key_exists and sent_key_exists(key):
            continue

        send_notification(
            build_escalation_notification(
                acknowledgement,
                level=level,
                recipient_user_id=recipient_user_id,
                recipient_email=recipient_email,
            ),
            sink=notification_sink,
        )

        if record_sent_key:
            record_sent_key(key)

        sent += 1

    return sent
