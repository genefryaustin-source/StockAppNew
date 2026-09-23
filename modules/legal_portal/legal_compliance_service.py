from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, Mapping, Optional

from .legal_notifications import (
    NotificationSink,
    overdue_notification,
    send_notification,
)
from .legal_registry import DOCUMENTS
from .legal_workflow_models import (
    AcknowledgementStatus,
    LegalAcknowledgement,
)
from .legal_workflow_service import LegalWorkflowService


@dataclass(frozen=True)
class LegalComplianceMetrics:
    total_assignments: int
    pending: int
    accepted: int
    declined: int
    expired: int
    overdue: int
    completion_rate: float
    acceptance_rate: float


@dataclass(frozen=True)
class LegalAccessDecision:
    allowed: bool
    reason: str
    pending_acknowledgement_ids: tuple[str, ...]


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


def is_overdue(
    acknowledgement: LegalAcknowledgement,
    *,
    now: datetime | None = None,
) -> bool:
    if acknowledgement.status != AcknowledgementStatus.PENDING:
        return False

    due_at = _parse_datetime(acknowledgement.due_at)
    if due_at is None:
        return False

    current = now or datetime.now(timezone.utc)
    return due_at < current


def calculate_metrics(
    acknowledgements: Iterable[LegalAcknowledgement],
    *,
    now: datetime | None = None,
) -> LegalComplianceMetrics:
    records = list(acknowledgements)
    total = len(records)

    pending = sum(
        item.status == AcknowledgementStatus.PENDING
        for item in records
    )
    accepted = sum(
        item.status == AcknowledgementStatus.ACCEPTED
        for item in records
    )
    declined = sum(
        item.status == AcknowledgementStatus.DECLINED
        for item in records
    )
    expired = sum(
        item.status == AcknowledgementStatus.EXPIRED
        for item in records
    )
    overdue = sum(
        is_overdue(item, now=now)
        for item in records
    )

    completed = accepted + declined + expired

    completion_rate = (
        round((completed / total) * 100.0, 2)
        if total
        else 100.0
    )
    acceptance_rate = (
        round((accepted / completed) * 100.0, 2)
        if completed
        else 0.0
    )

    return LegalComplianceMetrics(
        total_assignments=total,
        pending=pending,
        accepted=accepted,
        declined=declined,
        expired=expired,
        overdue=overdue,
        completion_rate=completion_rate,
        acceptance_rate=acceptance_rate,
    )


def evaluate_access(
    *,
    acknowledgements: Iterable[LegalAcknowledgement],
    required_document_keys: Iterable[str],
    block_on_decline: bool = True,
    block_on_overdue: bool = True,
) -> LegalAccessDecision:
    required = set(required_document_keys)
    relevant = [
        item
        for item in acknowledgements
        if item.document_key in required
    ]

    blocking: list[str] = []

    for item in relevant:
        if item.status == AcknowledgementStatus.PENDING:
            if block_on_overdue and is_overdue(item):
                blocking.append(item.id)
        elif (
            item.status == AcknowledgementStatus.DECLINED
            and block_on_decline
        ):
            blocking.append(item.id)

    if blocking:
        return LegalAccessDecision(
            allowed=False,
            reason=(
                "Required legal acknowledgements are overdue or were declined."
            ),
            pending_acknowledgement_ids=tuple(blocking),
        )

    return LegalAccessDecision(
        allowed=True,
        reason="No blocking legal acknowledgements were found.",
        pending_acknowledgement_ids=(),
    )


def send_overdue_notifications(
    *,
    service: LegalWorkflowService,
    user_email_resolver: Callable[[str], str | None] | None = None,
    notification_sink: NotificationSink | None = None,
    tenant_id: str | None = None,
) -> int:
    acknowledgements = service.repository.list_acknowledgements(
        tenant_id=tenant_id,
    )

    count = 0

    for item in acknowledgements:
        if not is_overdue(item):
            continue

        document = DOCUMENTS.get(item.document_key)
        title = document.title if document else item.document_key
        email = (
            user_email_resolver(item.user_id)
            if user_email_resolver
            else None
        )

        send_notification(
            overdue_notification(
                user_id=item.user_id,
                email=email,
                tenant_id=item.tenant_id,
                document_key=item.document_key,
                document_title=title,
                document_version=item.document_version,
                acknowledgement_id=item.id,
                due_at=item.due_at,
            ),
            sink=notification_sink,
        )
        count += 1

    return count
