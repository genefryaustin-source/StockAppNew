from __future__ import annotations

from .legal_registry import iter_documents
from .legal_workflow_models import LegalDocumentStatus
from .legal_workflow_service import LegalWorkflowService


def seed_registered_documents(
    service: LegalWorkflowService,
    *,
    actor_user_id: str | None = "system",
    tenant_id: str | None = None,
    publish: bool = False,
) -> list[str]:
    created_ids: list[str] = []
    existing = {
        (item.document_key, item.version)
        for item in service.repository.list_versions()
    }

    for document in iter_documents():
        key = (document.key, document.version)

        if key in existing:
            continue

        record = service.create_version(
            document_key=document.key,
            version=document.version,
            effective_date=document.effective_date,
            summary=document.summary,
            actor_user_id=actor_user_id,
            tenant_id=tenant_id,
        )
        created_ids.append(record.id)

        if publish:
            service.transition(
                version_id=record.id,
                target_status=LegalDocumentStatus.IN_REVIEW,
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
            service.transition(
                version_id=record.id,
                target_status=LegalDocumentStatus.APPROVED,
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )
            service.transition(
                version_id=record.id,
                target_status=LegalDocumentStatus.PUBLISHED,
                actor_user_id=actor_user_id,
                tenant_id=tenant_id,
            )

    return created_ids
