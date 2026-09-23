from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from .legal_audit import emit_legal_event
from .legal_workflow_models import (
    AcknowledgementStatus,
    LegalDocumentStatus,
    LegalReviewDecision,
)
from .legal_workflow_repository import LegalWorkflowRepository


ALLOWED_TRANSITIONS: dict[LegalDocumentStatus, set[LegalDocumentStatus]] = {
    LegalDocumentStatus.DRAFT: {
        LegalDocumentStatus.IN_REVIEW,
        LegalDocumentStatus.RETIRED,
    },
    LegalDocumentStatus.IN_REVIEW: {
        LegalDocumentStatus.CHANGES_REQUESTED,
        LegalDocumentStatus.APPROVED,
        LegalDocumentStatus.RETIRED,
    },
    LegalDocumentStatus.CHANGES_REQUESTED: {
        LegalDocumentStatus.DRAFT,
        LegalDocumentStatus.IN_REVIEW,
        LegalDocumentStatus.RETIRED,
    },
    LegalDocumentStatus.APPROVED: {
        LegalDocumentStatus.PUBLISHED,
        LegalDocumentStatus.RETIRED,
    },
    LegalDocumentStatus.PUBLISHED: {
        LegalDocumentStatus.RETIRED,
    },
    LegalDocumentStatus.RETIRED: set(),
}


class LegalWorkflowError(RuntimeError):
    pass


class LegalWorkflowService:
    def __init__(self, repository: LegalWorkflowRepository, audit_sink=None) -> None:
        self.repository = repository
        self.audit_sink = audit_sink

    def create_version(
        self,
        *,
        document_key: str,
        version: str,
        effective_date: str,
        summary: str,
        actor_user_id: str | None,
        tenant_id: str | None = None,
    ):
        record = self.repository.create_version(
            document_key=document_key,
            version=version,
            effective_date=effective_date,
            summary=summary,
            created_by=actor_user_id,
        )
        emit_legal_event(
            "LEGAL_VERSION_CREATED",
            document_key=document_key,
            user_id=actor_user_id,
            tenant_id=tenant_id,
            metadata={"version_id": record.id, "version": record.version},
            sink=self.audit_sink,
        )
        return record

    def transition(
        self,
        *,
        version_id: str,
        target_status: LegalDocumentStatus,
        actor_user_id: str | None,
        tenant_id: str | None = None,
    ):
        current = self.repository.get_version(version_id)
        if current is None:
            raise LegalWorkflowError("Legal document version not found.")

        allowed = ALLOWED_TRANSITIONS.get(current.status, set())
        if target_status not in allowed:
            raise LegalWorkflowError(
                f"Transition from {current.status.value} to "
                f"{target_status.value} is not permitted."
            )

        updated = self.repository.update_status(
            version_id,
            target_status,
            actor_user_id=actor_user_id,
        )
        emit_legal_event(
            "LEGAL_VERSION_STATUS_CHANGED",
            document_key=updated.document_key,
            user_id=actor_user_id,
            tenant_id=tenant_id,
            metadata={
                "version_id": updated.id,
                "version": updated.version,
                "previous_status": current.status.value,
                "new_status": updated.status.value,
            },
            sink=self.audit_sink,
        )
        return updated

    def record_review(
        self,
        *,
        version_id: str,
        reviewer_user_id: str,
        decision: LegalReviewDecision,
        comments: str,
        tenant_id: str | None = None,
    ):
        review = self.repository.add_review(
            version_id=version_id,
            reviewer_user_id=reviewer_user_id,
            decision=decision,
            comments=comments,
        )

        if decision == LegalReviewDecision.APPROVE:
            target = LegalDocumentStatus.APPROVED
        else:
            target = LegalDocumentStatus.CHANGES_REQUESTED

        current = self.repository.get_version(version_id)
        if current and target in ALLOWED_TRANSITIONS.get(current.status, set()):
            self.repository.update_status(
                version_id,
                target,
                actor_user_id=reviewer_user_id,
            )

        emit_legal_event(
            "LEGAL_REVIEW_RECORDED",
            document_key=current.document_key if current else None,
            user_id=reviewer_user_id,
            tenant_id=tenant_id,
            metadata={
                "version_id": version_id,
                "decision": decision.value,
                "comments": comments,
            },
            sink=self.audit_sink,
        )
        return review

    def request_acknowledgements(
        self,
        *,
        document_key: str,
        document_version: str,
        users: Iterable[tuple[str, str | None]],
        due_at: str | None,
        actor_user_id: str | None,
        tenant_id: str | None = None,
    ):
        records = [
            self.repository.request_acknowledgement(
                document_key=document_key,
                document_version=document_version,
                user_id=user_id,
                tenant_id=user_tenant_id,
                due_at=due_at,
            )
            for user_id, user_tenant_id in users
        ]

        emit_legal_event(
            "LEGAL_ACKNOWLEDGEMENTS_REQUESTED",
            document_key=document_key,
            user_id=actor_user_id,
            tenant_id=tenant_id,
            metadata={
                "document_version": document_version,
                "recipient_count": len(records),
                "due_at": due_at,
            },
            sink=self.audit_sink,
        )
        return records

    def respond_to_acknowledgement(
        self,
        *,
        acknowledgement_id: str,
        status: AcknowledgementStatus,
        user_id: str,
        tenant_id: str | None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ):
        current = next(
            (
                item
                for item in self.repository.list_acknowledgements(user_id=user_id)
                if item.id == acknowledgement_id
            ),
            None,
        )
        if current is None:
            raise LegalWorkflowError("Acknowledgement not found for this user.")

        updated = self.repository.respond_to_acknowledgement(
            acknowledgement_id,
            status=status,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        emit_legal_event(
            "LEGAL_ACKNOWLEDGEMENT_RESPONDED",
            document_key=updated.document_key,
            user_id=user_id,
            tenant_id=tenant_id,
            metadata={
                "acknowledgement_id": updated.id,
                "document_version": updated.document_version,
                "status": updated.status.value,
            },
            sink=self.audit_sink,
        )
        return updated
