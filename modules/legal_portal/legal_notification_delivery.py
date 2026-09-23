from __future__ import annotations

import hashlib
from typing import Callable

from .legal_notification_repository import SqlAlchemyLegalNotificationRepository
from .legal_notifications import LegalNotification, NotificationSink


def stable_notification_key(notification: LegalNotification) -> str:
    raw = "|".join(
        [
            notification.notification_type.value,
            notification.recipient_user_id,
            notification.document_key or "",
            notification.document_version or "",
            notification.acknowledgement_id or "",
            notification.subject,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_persistent_notification_sink(
    *,
    repository: SqlAlchemyLegalNotificationRepository,
    delivery_sink: NotificationSink,
) -> NotificationSink:
    def sink(notification: LegalNotification) -> None:
        key = stable_notification_key(notification)
        if repository.exists(key):
            return

        delivery_id = repository.record_pending(
            notification_key=key,
            notification=notification,
        )

        try:
            delivery_sink(notification)
            repository.mark_delivered(delivery_id)
        except Exception as exc:
            repository.mark_failed(delivery_id, str(exc))
            raise

    return sink
