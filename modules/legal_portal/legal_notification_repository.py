from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .legal_notifications import LegalNotification
from .legal_operations_db_models import LegalNotificationDeliveryModel


class LegalNotificationPersistenceError(RuntimeError):
    pass


class SqlAlchemyLegalNotificationRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def exists(self, notification_key: str) -> bool:
        with self._session_factory() as session:
            statement = select(LegalNotificationDeliveryModel.id).where(
                LegalNotificationDeliveryModel.notification_key == notification_key
            )
            return session.scalar(statement) is not None

    def record_pending(
        self,
        *,
        notification_key: str,
        notification: LegalNotification,
    ) -> str:
        model = LegalNotificationDeliveryModel(
            id=str(uuid4()),
            notification_key=notification_key,
            notification_type=notification.notification_type.value,
            recipient_user_id=notification.recipient_user_id,
            recipient_email=notification.recipient_email,
            acknowledgement_id=notification.acknowledgement_id,
            document_key=notification.document_key,
            status="pending",
            created_at=datetime.now(timezone.utc),
            metadata_json=json.dumps(
                {
                    "subject": notification.subject,
                    "tenant_id": notification.tenant_id,
                    "document_version": notification.document_version,
                },
                sort_keys=True,
            ),
        )
        with self._session_factory() as session:
            try:
                session.add(model)
                session.commit()
                return model.id
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(LegalNotificationDeliveryModel.id).where(
                        LegalNotificationDeliveryModel.notification_key == notification_key
                    )
                )
                if existing:
                    return existing
                raise
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalNotificationPersistenceError("Unable to record pending notification.") from exc

    def mark_delivered(self, delivery_id: str) -> None:
        with self._session_factory() as session:
            model = session.get(LegalNotificationDeliveryModel, delivery_id)
            if model is None:
                return
            model.status = "delivered"
            model.delivered_at = datetime.now(timezone.utc)
            model.error_message = None
            session.commit()

    def mark_failed(self, delivery_id: str, error_message: str) -> None:
        with self._session_factory() as session:
            model = session.get(LegalNotificationDeliveryModel, delivery_id)
            if model is None:
                return
            model.status = "failed"
            model.error_message = error_message[:4000]
            session.commit()
