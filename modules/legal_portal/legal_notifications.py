from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping, Optional


logger = logging.getLogger("aiqintellus.legal_portal.notifications")


class LegalNotificationType(str, Enum):
    ACKNOWLEDGEMENT_ASSIGNED = "acknowledgement_assigned"
    ACKNOWLEDGEMENT_DUE_SOON = "acknowledgement_due_soon"
    ACKNOWLEDGEMENT_OVERDUE = "acknowledgement_overdue"
    REVIEW_ASSIGNED = "review_assigned"
    REVIEW_COMPLETED = "review_completed"
    VERSION_PUBLISHED = "version_published"
    VERSION_RETIRED = "version_retired"


@dataclass(frozen=True)
class LegalNotification:
    notification_type: LegalNotificationType
    recipient_user_id: str
    recipient_email: str | None
    subject: str
    message: str
    document_key: str | None = None
    document_version: str | None = None
    acknowledgement_id: str | None = None
    tenant_id: str | None = None
    created_at: str = ""


NotificationSink = Callable[[LegalNotification], None]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_notification_sink(notification: LegalNotification) -> None:
    logger.info(
        "LEGAL_NOTIFICATION type=%s recipient=%s subject=%s",
        notification.notification_type.value,
        notification.recipient_user_id,
        notification.subject,
    )


def send_notification(
    notification: LegalNotification,
    *,
    sink: NotificationSink | None = None,
) -> None:
    resolved = notification

    if not resolved.created_at:
        resolved = LegalNotification(
            notification_type=notification.notification_type,
            recipient_user_id=notification.recipient_user_id,
            recipient_email=notification.recipient_email,
            subject=notification.subject,
            message=notification.message,
            document_key=notification.document_key,
            document_version=notification.document_version,
            acknowledgement_id=notification.acknowledgement_id,
            tenant_id=notification.tenant_id,
            created_at=utc_now_iso(),
        )

    (sink or default_notification_sink)(resolved)


def acknowledgement_assigned_notification(
    *,
    user_id: str,
    email: str | None,
    tenant_id: str | None,
    document_key: str,
    document_title: str,
    document_version: str,
    acknowledgement_id: str,
    due_at: str | None,
) -> LegalNotification:
    due_text = f" Due by {due_at}." if due_at else ""

    return LegalNotification(
        notification_type=LegalNotificationType.ACKNOWLEDGEMENT_ASSIGNED,
        recipient_user_id=user_id,
        recipient_email=email,
        subject=f"Review required: {document_title}",
        message=(
            f"You have been assigned {document_title}, version "
            f"{document_version}, for acknowledgement.{due_text}"
        ),
        document_key=document_key,
        document_version=document_version,
        acknowledgement_id=acknowledgement_id,
        tenant_id=tenant_id,
    )


def overdue_notification(
    *,
    user_id: str,
    email: str | None,
    tenant_id: str | None,
    document_key: str,
    document_title: str,
    document_version: str,
    acknowledgement_id: str,
    due_at: str | None,
) -> LegalNotification:
    return LegalNotification(
        notification_type=LegalNotificationType.ACKNOWLEDGEMENT_OVERDUE,
        recipient_user_id=user_id,
        recipient_email=email,
        subject=f"Overdue legal acknowledgement: {document_title}",
        message=(
            f"Your acknowledgement for {document_title}, version "
            f"{document_version}, is overdue. Due date: {due_at or 'not set'}."
        ),
        document_key=document_key,
        document_version=document_version,
        acknowledgement_id=acknowledgement_id,
        tenant_id=tenant_id,
    )
