from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .legal_escalation_models import LegalAccessOverride, LegalOverrideReason
from .legal_operations_db_models import LegalAccessOverrideModel


class LegalOverridePersistenceError(RuntimeError):
    pass


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class SqlAlchemyLegalOverrideRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _to_domain(model: LegalAccessOverrideModel) -> LegalAccessOverride:
        return LegalAccessOverride(
            id=model.id,
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            acknowledgement_id=model.acknowledgement_id,
            document_key=model.document_key,
            reason=LegalOverrideReason(model.reason),
            justification=model.justification,
            created_by=model.created_by,
            created_at=model.created_at.isoformat(),
            expires_at=model.expires_at.isoformat() if model.expires_at else None,
            revoked_at=model.revoked_at.isoformat() if model.revoked_at else None,
            revoked_by=model.revoked_by,
            metadata=model.metadata_dict(),
        )

    def create(
        self,
        *,
        user_id: str,
        tenant_id: str | None,
        acknowledgement_id: str | None,
        document_key: str | None,
        reason: LegalOverrideReason,
        justification: str,
        created_by: str,
        expires_at: str | None,
    ) -> LegalAccessOverride:
        model = LegalAccessOverrideModel(
            id=str(uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            acknowledgement_id=acknowledgement_id,
            document_key=document_key,
            reason=reason.value,
            justification=justification,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
            expires_at=_parse_datetime(expires_at),
            metadata_json="{}",
        )
        with self._session_factory() as session:
            try:
                session.add(model)
                session.commit()
                session.refresh(model)
                return self._to_domain(model)
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalOverridePersistenceError("Unable to create legal override.") from exc

    def list(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[LegalAccessOverride]:
        with self._session_factory() as session:
            statement = select(LegalAccessOverrideModel)
            if user_id:
                statement = statement.where(LegalAccessOverrideModel.user_id == user_id)
            if tenant_id:
                statement = statement.where(LegalAccessOverrideModel.tenant_id == tenant_id)
            statement = statement.order_by(LegalAccessOverrideModel.created_at.desc())
            return [self._to_domain(item) for item in session.scalars(statement).all()]

    def revoke(self, override_id: str, *, revoked_by: str) -> LegalAccessOverride:
        with self._session_factory() as session:
            model = session.get(LegalAccessOverrideModel, override_id)
            if model is None:
                raise KeyError(f"Unknown legal override: {override_id}")
            model.revoked_at = datetime.now(timezone.utc)
            model.revoked_by = revoked_by
            try:
                session.commit()
                session.refresh(model)
                return self._to_domain(model)
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalOverridePersistenceError("Unable to revoke legal override.") from exc
