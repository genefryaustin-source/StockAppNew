from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from threading import RLock
from typing import Iterable, Protocol
from uuid import uuid4

from .legal_workflow_models import (
    AcknowledgementStatus,
    LegalAcknowledgement,
    LegalDocumentStatus,
    LegalDocumentVersion,
    LegalReviewDecision,
    LegalReviewRecord,
    LegalWorkflowSummary,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LegalWorkflowRepository(Protocol):
    def create_version(
        self,
        *,
        document_key: str,
        version: str,
        effective_date: str,
        summary: str,
        created_by: str | None,
    ) -> LegalDocumentVersion: ...

    def list_versions(self, document_key: str | None = None) -> list[LegalDocumentVersion]: ...

    def get_version(self, version_id: str) -> LegalDocumentVersion | None: ...

    def update_status(
        self,
        version_id: str,
        status: LegalDocumentStatus,
        *,
        actor_user_id: str | None = None,
    ) -> LegalDocumentVersion: ...

    def add_review(
        self,
        *,
        version_id: str,
        reviewer_user_id: str,
        decision: LegalReviewDecision,
        comments: str,
    ) -> LegalReviewRecord: ...

    def list_reviews(self, version_id: str) -> list[LegalReviewRecord]: ...

    def request_acknowledgement(
        self,
        *,
        document_key: str,
        document_version: str,
        user_id: str,
        tenant_id: str | None,
        due_at: str | None,
    ) -> LegalAcknowledgement: ...

    def respond_to_acknowledgement(
        self,
        acknowledgement_id: str,
        *,
        status: AcknowledgementStatus,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LegalAcknowledgement: ...

    def list_acknowledgements(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        document_key: str | None = None,
    ) -> list[LegalAcknowledgement]: ...

    def summary(self) -> LegalWorkflowSummary: ...


class InMemoryLegalWorkflowRepository:
    def __init__(self) -> None:
        self._versions: dict[str, LegalDocumentVersion] = {}
        self._reviews: dict[str, LegalReviewRecord] = {}
        self._acknowledgements: dict[str, LegalAcknowledgement] = {}
        self._lock = RLock()

    def create_version(
        self,
        *,
        document_key: str,
        version: str,
        effective_date: str,
        summary: str,
        created_by: str | None,
    ) -> LegalDocumentVersion:
        with self._lock:
            record = LegalDocumentVersion(
                id=str(uuid4()),
                document_key=document_key,
                version=version,
                status=LegalDocumentStatus.DRAFT,
                effective_date=effective_date,
                summary=summary,
                created_at=utc_now(),
                created_by=created_by,
            )
            self._versions[record.id] = record
            return record

    def list_versions(self, document_key: str | None = None) -> list[LegalDocumentVersion]:
        with self._lock:
            records = list(self._versions.values())
            if document_key:
                records = [item for item in records if item.document_key == document_key]
            return sorted(records, key=lambda item: item.created_at, reverse=True)

    def get_version(self, version_id: str) -> LegalDocumentVersion | None:
        with self._lock:
            return self._versions.get(version_id)

    def update_status(
        self,
        version_id: str,
        status: LegalDocumentStatus,
        *,
        actor_user_id: str | None = None,
    ) -> LegalDocumentVersion:
        with self._lock:
            current = self._versions.get(version_id)
            if current is None:
                raise KeyError(f"Unknown legal document version: {version_id}")

            updates: dict[str, str | None] = {"status": status}
            now = utc_now()

            if status == LegalDocumentStatus.APPROVED:
                updates["approved_at"] = now
                updates["approved_by"] = actor_user_id
            elif status == LegalDocumentStatus.PUBLISHED:
                updates["published_at"] = now
            elif status == LegalDocumentStatus.RETIRED:
                updates["retired_at"] = now

            updated = replace(current, **updates)
            self._versions[version_id] = updated
            return updated

    def add_review(
        self,
        *,
        version_id: str,
        reviewer_user_id: str,
        decision: LegalReviewDecision,
        comments: str,
    ) -> LegalReviewRecord:
        with self._lock:
            if version_id not in self._versions:
                raise KeyError(f"Unknown legal document version: {version_id}")

            record = LegalReviewRecord(
                id=str(uuid4()),
                document_version_id=version_id,
                reviewer_user_id=reviewer_user_id,
                decision=decision,
                comments=comments,
                created_at=utc_now(),
            )
            self._reviews[record.id] = record
            return record

    def list_reviews(self, version_id: str) -> list[LegalReviewRecord]:
        with self._lock:
            records = [
                item
                for item in self._reviews.values()
                if item.document_version_id == version_id
            ]
            return sorted(records, key=lambda item: item.created_at, reverse=True)

    def request_acknowledgement(
        self,
        *,
        document_key: str,
        document_version: str,
        user_id: str,
        tenant_id: str | None,
        due_at: str | None,
    ) -> LegalAcknowledgement:
        with self._lock:
            existing = next(
                (
                    item
                    for item in self._acknowledgements.values()
                    if item.document_key == document_key
                    and item.document_version == document_version
                    and item.user_id == user_id
                    and item.status == AcknowledgementStatus.PENDING
                ),
                None,
            )
            if existing:
                return existing

            record = LegalAcknowledgement(
                id=str(uuid4()),
                document_key=document_key,
                document_version=document_version,
                user_id=user_id,
                tenant_id=tenant_id,
                status=AcknowledgementStatus.PENDING,
                requested_at=utc_now(),
                due_at=due_at,
            )
            self._acknowledgements[record.id] = record
            return record

    def respond_to_acknowledgement(
        self,
        acknowledgement_id: str,
        *,
        status: AcknowledgementStatus,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> LegalAcknowledgement:
        with self._lock:
            current = self._acknowledgements.get(acknowledgement_id)
            if current is None:
                raise KeyError(f"Unknown legal acknowledgement: {acknowledgement_id}")

            updated = replace(
                current,
                status=status,
                responded_at=utc_now(),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self._acknowledgements[acknowledgement_id] = updated
            return updated

    def list_acknowledgements(
        self,
        *,
        user_id: str | None = None,
        tenant_id: str | None = None,
        document_key: str | None = None,
    ) -> list[LegalAcknowledgement]:
        with self._lock:
            records = list(self._acknowledgements.values())

            if user_id:
                records = [item for item in records if item.user_id == user_id]
            if tenant_id:
                records = [item for item in records if item.tenant_id == tenant_id]
            if document_key:
                records = [item for item in records if item.document_key == document_key]

            return sorted(records, key=lambda item: item.requested_at, reverse=True)

    def summary(self) -> LegalWorkflowSummary:
        with self._lock:
            versions = list(self._versions.values())
            acknowledgements = list(self._acknowledgements.values())

            return LegalWorkflowSummary(
                total_versions=len(versions),
                drafts=sum(item.status == LegalDocumentStatus.DRAFT for item in versions),
                in_review=sum(item.status == LegalDocumentStatus.IN_REVIEW for item in versions),
                approved=sum(item.status == LegalDocumentStatus.APPROVED for item in versions),
                published=sum(item.status == LegalDocumentStatus.PUBLISHED for item in versions),
                retired=sum(item.status == LegalDocumentStatus.RETIRED for item in versions),
                pending_acknowledgements=sum(
                    item.status == AcknowledgementStatus.PENDING
                    for item in acknowledgements
                ),
                accepted_acknowledgements=sum(
                    item.status == AcknowledgementStatus.ACCEPTED
                    for item in acknowledgements
                ),
                declined_acknowledgements=sum(
                    item.status == AcknowledgementStatus.DECLINED
                    for item in acknowledgements
                ),
            )


_DEFAULT_REPOSITORY = InMemoryLegalWorkflowRepository()


def get_legal_workflow_repository() -> InMemoryLegalWorkflowRepository:
    return _DEFAULT_REPOSITORY
