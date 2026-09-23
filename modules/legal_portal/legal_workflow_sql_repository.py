from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from .legal_workflow_db_models import (
    LegalAcknowledgementModel,
    LegalDocumentVersionModel,
    LegalReviewModel,
)
from .legal_workflow_models import (
    AcknowledgementStatus,
    LegalAcknowledgement,
    LegalDocumentStatus,
    LegalDocumentVersion,
    LegalReviewDecision,
    LegalReviewRecord,
    LegalWorkflowSummary,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LegalWorkflowPersistenceError(RuntimeError):
    pass


class SqlAlchemyLegalWorkflowRepository:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _version_to_domain(
        model: LegalDocumentVersionModel,
    ) -> LegalDocumentVersion:
        return LegalDocumentVersion(
            id=model.id,
            document_key=model.document_key,
            version=model.version,
            status=LegalDocumentStatus(model.status),
            effective_date=model.effective_date,
            summary=model.summary,
            created_at=model.created_at.isoformat(),
            created_by=model.created_by,
            approved_at=(
                model.approved_at.isoformat()
                if model.approved_at
                else None
            ),
            approved_by=model.approved_by,
            published_at=(
                model.published_at.isoformat()
                if model.published_at
                else None
            ),
            retired_at=(
                model.retired_at.isoformat()
                if model.retired_at
                else None
            ),
            metadata=model.metadata_dict(),
        )

    @staticmethod
    def _review_to_domain(model: LegalReviewModel) -> LegalReviewRecord:
        return LegalReviewRecord(
            id=model.id,
            document_version_id=model.document_version_id,
            reviewer_user_id=model.reviewer_user_id,
            decision=LegalReviewDecision(model.decision),
            comments=model.comments,
            created_at=model.created_at.isoformat(),
        )

    @staticmethod
    def _ack_to_domain(
        model: LegalAcknowledgementModel,
    ) -> LegalAcknowledgement:
        return LegalAcknowledgement(
            id=model.id,
            document_key=model.document_key,
            document_version=model.document_version,
            user_id=model.user_id,
            tenant_id=model.tenant_id,
            status=AcknowledgementStatus(model.status),
            requested_at=model.requested_at.isoformat(),
            due_at=model.due_at,
            responded_at=(
                model.responded_at.isoformat()
                if model.responded_at
                else None
            ),
            ip_address=model.ip_address,
            user_agent=model.user_agent,
            metadata=model.metadata_dict(),
        )

    def create_version(
        self,
        *,
        document_key: str,
        version: str,
        effective_date: str,
        summary: str,
        created_by: str | None,
    ) -> LegalDocumentVersion:
        model = LegalDocumentVersionModel(
            id=str(uuid4()),
            document_key=document_key,
            version=version,
            status=LegalDocumentStatus.DRAFT.value,
            effective_date=effective_date,
            summary=summary,
            created_at=utc_now(),
            created_by=created_by,
            metadata_json="{}",
        )

        with self._session_factory() as session:
            try:
                session.add(model)
                session.commit()
                session.refresh(model)
                return self._version_to_domain(model)
            except IntegrityError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    f"Version {version!r} already exists for "
                    f"document {document_key!r}."
                ) from exc
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    "Unable to create legal document version."
                ) from exc

    def list_versions(
        self,
        document_key: str | None = None,
    ) -> list[LegalDocumentVersion]:
        with self._session_factory() as session:
            statement = select(LegalDocumentVersionModel)

            if document_key:
                statement = statement.where(
                    LegalDocumentVersionModel.document_key == document_key
                )

            statement = statement.order_by(
                LegalDocumentVersionModel.created_at.desc()
            )

            models = session.scalars(statement).all()
            return [self._version_to_domain(model) for model in models]

    def get_version(
        self,
        version_id: str,
    ) -> LegalDocumentVersion | None:
        with self._session_factory() as session:
            model = session.get(LegalDocumentVersionModel, version_id)
            return self._version_to_domain(model) if model else None

    def update_status(
        self,
        version_id: str,
        status: LegalDocumentStatus,
        *,
        actor_user_id: str | None = None,
    ) -> LegalDocumentVersion:
        with self._session_factory() as session:
            model = session.get(LegalDocumentVersionModel, version_id)

            if model is None:
                raise KeyError(f"Unknown legal document version: {version_id}")

            model.status = status.value
            now = utc_now()

            if status == LegalDocumentStatus.APPROVED:
                model.approved_at = now
                model.approved_by = actor_user_id
            elif status == LegalDocumentStatus.PUBLISHED:
                model.published_at = now
            elif status == LegalDocumentStatus.RETIRED:
                model.retired_at = now

            try:
                session.commit()
                session.refresh(model)
                return self._version_to_domain(model)
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    "Unable to update legal document status."
                ) from exc

    def add_review(
        self,
        *,
        version_id: str,
        reviewer_user_id: str,
        decision: LegalReviewDecision,
        comments: str,
    ) -> LegalReviewRecord:
        model = LegalReviewModel(
            id=str(uuid4()),
            document_version_id=version_id,
            reviewer_user_id=reviewer_user_id,
            decision=decision.value,
            comments=comments,
            created_at=utc_now(),
        )

        with self._session_factory() as session:
            if session.get(LegalDocumentVersionModel, version_id) is None:
                raise KeyError(
                    f"Unknown legal document version: {version_id}"
                )

            try:
                session.add(model)
                session.commit()
                session.refresh(model)
                return self._review_to_domain(model)
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    "Unable to save legal review."
                ) from exc

    def list_reviews(
        self,
        version_id: str,
    ) -> list[LegalReviewRecord]:
        with self._session_factory() as session:
            statement = (
                select(LegalReviewModel)
                .where(
                    LegalReviewModel.document_version_id == version_id
                )
                .order_by(LegalReviewModel.created_at.desc())
            )
            models = session.scalars(statement).all()
            return [self._review_to_domain(model) for model in models]

    def request_acknowledgement(
        self,
        *,
        document_key: str,
        document_version: str,
        user_id: str,
        tenant_id: str | None,
        due_at: str | None,
    ) -> LegalAcknowledgement:
        with self._session_factory() as session:
            existing_statement = select(
                LegalAcknowledgementModel
            ).where(
                LegalAcknowledgementModel.document_key == document_key,
                LegalAcknowledgementModel.document_version
                == document_version,
                LegalAcknowledgementModel.user_id == user_id,
            )
            existing = session.scalar(existing_statement)

            if existing is not None:
                return self._ack_to_domain(existing)

            model = LegalAcknowledgementModel(
                id=str(uuid4()),
                document_key=document_key,
                document_version=document_version,
                user_id=user_id,
                tenant_id=tenant_id,
                status=AcknowledgementStatus.PENDING.value,
                requested_at=utc_now(),
                due_at=due_at,
                metadata_json="{}",
            )

            try:
                session.add(model)
                session.commit()
                session.refresh(model)
                return self._ack_to_domain(model)
            except IntegrityError:
                session.rollback()
                existing = session.scalar(existing_statement)

                if existing is not None:
                    return self._ack_to_domain(existing)

                raise LegalWorkflowPersistenceError(
                    "Unable to create legal acknowledgement."
                )
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    "Unable to create legal acknowledgement."
                ) from exc

    def respond_to_acknowledgement(
        self,
        acknowledgement_id: str,
        *,
        status: AcknowledgementStatus,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LegalAcknowledgement:
        with self._session_factory() as session:
            model = session.get(
                LegalAcknowledgementModel,
                acknowledgement_id,
            )

            if model is None:
                raise KeyError(
                    f"Unknown legal acknowledgement: "
                    f"{acknowledgement_id}"
                )

            model.status = status.value
            model.responded_at = utc_now()
            model.ip_address = ip_address
            model.user_agent = user_agent

            try:
                session.commit()
                session.refresh(model)
                return self._ack_to_domain(model)
            except SQLAlchemyError as exc:
                session.rollback()
                raise LegalWorkflowPersistenceError(
                    "Unable to record acknowledgement response."
                ) from exc

    def list_acknowledgements(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        document_key: str | None = None,
    ) -> list[LegalAcknowledgement]:
        with self._session_factory() as session:
            statement = select(LegalAcknowledgementModel)

            if user_id:
                statement = statement.where(
                    LegalAcknowledgementModel.user_id == user_id
                )
            if tenant_id:
                statement = statement.where(
                    LegalAcknowledgementModel.tenant_id == tenant_id
                )
            if document_key:
                statement = statement.where(
                    LegalAcknowledgementModel.document_key == document_key
                )

            statement = statement.order_by(
                LegalAcknowledgementModel.requested_at.desc()
            )

            models = session.scalars(statement).all()
            return [self._ack_to_domain(model) for model in models]

    def summary(self) -> LegalWorkflowSummary:
        with self._session_factory() as session:
            status_counts = dict(
                session.execute(
                    select(
                        LegalDocumentVersionModel.status,
                        func.count(LegalDocumentVersionModel.id),
                    ).group_by(LegalDocumentVersionModel.status)
                ).all()
            )

            acknowledgement_counts = dict(
                session.execute(
                    select(
                        LegalAcknowledgementModel.status,
                        func.count(LegalAcknowledgementModel.id),
                    ).group_by(LegalAcknowledgementModel.status)
                ).all()
            )

            total_versions = sum(status_counts.values())

            return LegalWorkflowSummary(
                total_versions=total_versions,
                drafts=status_counts.get(
                    LegalDocumentStatus.DRAFT.value,
                    0,
                ),
                in_review=status_counts.get(
                    LegalDocumentStatus.IN_REVIEW.value,
                    0,
                ),
                approved=status_counts.get(
                    LegalDocumentStatus.APPROVED.value,
                    0,
                ),
                published=status_counts.get(
                    LegalDocumentStatus.PUBLISHED.value,
                    0,
                ),
                retired=status_counts.get(
                    LegalDocumentStatus.RETIRED.value,
                    0,
                ),
                pending_acknowledgements=acknowledgement_counts.get(
                    AcknowledgementStatus.PENDING.value,
                    0,
                ),
                accepted_acknowledgements=acknowledgement_counts.get(
                    AcknowledgementStatus.ACCEPTED.value,
                    0,
                ),
                declined_acknowledgements=acknowledgement_counts.get(
                    AcknowledgementStatus.DECLINED.value,
                    0,
                ),
            )
