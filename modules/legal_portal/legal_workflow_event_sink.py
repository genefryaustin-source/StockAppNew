from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from typing import Callable
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from .legal_audit import LegalAuditEvent
from .legal_workflow_db_models import LegalWorkflowEventModel


def build_sql_legal_audit_sink(
    session_factory: Callable[[], Session],
):
    def sink(event: LegalAuditEvent) -> None:
        metadata = dict(event.metadata or {})

        model = LegalWorkflowEventModel(
            id=str(uuid4()),
            event_type=event.event_type,
            document_key=event.document_key,
            document_version_id=metadata.get("version_id"),
            acknowledgement_id=metadata.get("acknowledgement_id"),
            actor_user_id=event.user_id,
            tenant_id=event.tenant_id,
            occurred_at=datetime.fromisoformat(event.occurred_at),
            metadata_json=json.dumps(
                metadata,
                sort_keys=True,
                default=str,
            ),
        )

        with session_factory() as session:
            try:
                session.add(model)
                session.commit()
            except SQLAlchemyError:
                session.rollback()
                raise

    return sink
