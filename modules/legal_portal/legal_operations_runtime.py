from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from .legal_notification_delivery import build_persistent_notification_sink
from .legal_notification_repository import SqlAlchemyLegalNotificationRepository
from .legal_notifications import NotificationSink, default_notification_sink
from .legal_override_service import (
    InMemoryLegalOverrideRepository,
    LegalOverrideService,
)
from .legal_override_sql_repository import SqlAlchemyLegalOverrideRepository


@dataclass(frozen=True)
class LegalOperationsRuntime:
    override_service: LegalOverrideService
    notification_sink: NotificationSink
    persistence_mode: str


def build_legal_operations_runtime(
    *,
    session_factory: Callable[[], Session] | None = None,
    delivery_sink: NotificationSink | None = None,
) -> LegalOperationsRuntime:
    resolved_delivery = delivery_sink or default_notification_sink

    if session_factory is None:
        repository = InMemoryLegalOverrideRepository()
        return LegalOperationsRuntime(
            override_service=LegalOverrideService(repository),
            notification_sink=resolved_delivery,
            persistence_mode="memory",
        )

    override_repository = SqlAlchemyLegalOverrideRepository(session_factory)
    notification_repository = SqlAlchemyLegalNotificationRepository(session_factory)

    return LegalOperationsRuntime(
        override_service=LegalOverrideService(override_repository),
        notification_sink=build_persistent_notification_sink(
            repository=notification_repository,
            delivery_sink=resolved_delivery,
        ),
        persistence_mode="sqlalchemy",
    )
