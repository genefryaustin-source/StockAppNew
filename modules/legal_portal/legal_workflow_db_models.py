from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LegalWorkflowBase(DeclarativeBase):
    pass


class LegalDocumentVersionModel(LegalWorkflowBase):
    __tablename__ = "legal_document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_key",
            "version",
            name="uq_legal_document_versions_key_version",
        ),
        Index(
            "ix_legal_document_versions_status",
            "status",
        ),
        Index(
            "ix_legal_document_versions_document_key",
            "document_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_key: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    effective_date: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    created_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    retired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    reviews: Mapped[list["LegalReviewModel"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
    )

    def metadata_dict(self) -> dict[str, Any]:
        try:
            value = json.loads(self.metadata_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}


class LegalReviewModel(LegalWorkflowBase):
    __tablename__ = "legal_document_reviews"
    __table_args__ = (
        Index(
            "ix_legal_document_reviews_version",
            "document_version_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey(
            "legal_document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    reviewer_user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    comments: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    document_version: Mapped[LegalDocumentVersionModel] = relationship(
        back_populates="reviews",
    )


class LegalAcknowledgementModel(LegalWorkflowBase):
    __tablename__ = "legal_acknowledgements"
    __table_args__ = (
        UniqueConstraint(
            "document_key",
            "document_version",
            "user_id",
            name="uq_legal_ack_document_version_user",
        ),
        Index(
            "ix_legal_ack_user_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_legal_ack_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_legal_ack_document_key",
            "document_key",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_key: Mapped[str] = mapped_column(String(160), nullable=False)
    document_version: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str] = mapped_column(String(160), nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    due_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ip_address: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    def metadata_dict(self) -> dict[str, Any]:
        try:
            value = json.loads(self.metadata_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}


class LegalWorkflowEventModel(LegalWorkflowBase):
    __tablename__ = "legal_workflow_events"
    __table_args__ = (
        Index(
            "ix_legal_workflow_events_type",
            "event_type",
        ),
        Index(
            "ix_legal_workflow_events_document",
            "document_key",
        ),
        Index(
            "ix_legal_workflow_events_tenant",
            "tenant_id",
        ),
        Index(
            "ix_legal_workflow_events_occurred",
            "occurred_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    document_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    document_version_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    acknowledgement_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    actor_user_id: Mapped[str | None] = mapped_column(
        String(160),
        nullable=True,
    )
    tenant_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
