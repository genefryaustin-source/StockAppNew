from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from .legal_escalation_models import LegalEvidencePackage
from .legal_registry import DOCUMENTS
from .legal_workflow_service import LegalWorkflowService


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_evidence_package(
    *,
    service: LegalWorkflowService,
    generated_by: str,
    user_id: str | None = None,
    tenant_id: str | None = None,
    document_key: str | None = None,
) -> LegalEvidencePackage:
    acknowledgements = service.repository.list_acknowledgements(
        user_id=user_id,
        tenant_id=tenant_id,
        document_key=document_key,
    )

    versions = service.repository.list_versions(document_key=document_key)

    reviews = []

    for version in versions:
        reviews.extend(
            asdict(item)
            for item in service.repository.list_reviews(version.id)
        )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": generated_by,
        "filters": {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "document_key": document_key,
        },
        "documents": {
            key: {
                "title": document.title,
                "version": document.version,
                "effective_date": document.effective_date,
            }
            for key, document in DOCUMENTS.items()
            if document_key is None or key == document_key
        },
        "versions": [asdict(item) for item in versions],
        "reviews": reviews,
        "acknowledgements": [
            asdict(item)
            for item in acknowledgements
        ],
    }

    payload["evidence_sha256"] = _stable_hash(payload)

    return LegalEvidencePackage(
        generated_at=payload["generated_at"],
        generated_by=generated_by,
        user_id=user_id,
        tenant_id=tenant_id,
        document_key=document_key,
        payload=payload,
    )


def evidence_package_json(
    package: LegalEvidencePackage,
) -> str:
    return json.dumps(
        package.payload,
        indent=2,
        sort_keys=True,
        default=str,
    )
