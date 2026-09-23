from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .legal_workflow_db_models import LegalWorkflowBase


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LegalAccessOverrideModel(LegalWorkflowBase):
    __tablename__ = "legal_access_overrides"
    __table_args__ = (
        Index("ix_legal_access_overrides_user", "user_id"),
        Index("ix_legal_access_overrides_tenant", "tenant_id"),
        Index("ix_legal_access_overrides_document", "document_key"),
        Index("ix_legal_access_overrides_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    acknowledgement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    document_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def metadata_dict(self) -> dict[str, Any]:
        try:
            value = json.loads(self.metadata_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}


class LegalNotificationDeliveryModel(LegalWorkflowBase):
    __tablename__ = "legal_notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_key", name="uq_legal_notification_delivery_key"),
        Index("ix_legal_notification_deliveries_recipient", "recipient_user_id"),
        Index("ix_legal_notification_deliveries_status", "status"),
        Index("ix_legal_notification_deliveries_ack", "acknowledgement_id"),
        Index("ix_legal_notification_deliveries_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notification_key: Mapped[str] = mapped_column(String(128), nullable=False)
    notification_type: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    acknowledgement_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    document_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def metadata_dict(self) -> dict[str, Any]:
        try:
            value = json.loads(self.metadata_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}
