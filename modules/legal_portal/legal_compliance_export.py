from __future__ import annotations

import csv
import io

from .legal_compliance_service import is_overdue
from .legal_registry import DOCUMENTS
from .legal_workflow_models import LegalAcknowledgement


def acknowledgements_to_csv(
    acknowledgements: list[LegalAcknowledgement],
) -> str:
    output = io.StringIO()

    writer = csv.DictWriter(
        output,
        fieldnames=[
            "document_key",
            "document_title",
            "document_version",
            "user_id",
            "tenant_id",
            "status",
            "requested_at",
            "due_at",
            "responded_at",
            "overdue",
        ],
    )
    writer.writeheader()

    for item in acknowledgements:
        document = DOCUMENTS.get(item.document_key)

        writer.writerow(
            {
                "document_key": item.document_key,
                "document_title": (
                    document.title
                    if document
                    else item.document_key
                ),
                "document_version": item.document_version,
                "user_id": item.user_id,
                "tenant_id": item.tenant_id or "",
                "status": item.status.value,
                "requested_at": item.requested_at,
                "due_at": item.due_at or "",
                "responded_at": item.responded_at or "",
                "overdue": is_overdue(item),
            }
        )

    return output.getvalue()
