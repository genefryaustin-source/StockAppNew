from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional


logger = logging.getLogger("aiqintellus.legal_portal.audit")


@dataclass(frozen=True)
class LegalAuditEvent:
    event_type: str
    occurred_at: str
    document_key: str | None
    user_id: str | None
    tenant_id: str | None
    metadata: Mapping[str, Any]


AuditSink = Callable[[LegalAuditEvent], None]


def build_event(
    event_type: str,
    *,
    document_key: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> LegalAuditEvent:
    return LegalAuditEvent(
        event_type=event_type,
        occurred_at=datetime.now(timezone.utc).isoformat(),
        document_key=document_key,
        user_id=user_id,
        tenant_id=tenant_id,
        metadata=dict(metadata or {}),
    )


def default_audit_sink(event: LegalAuditEvent) -> None:
    logger.info("LEGAL_AUDIT %s", json.dumps(asdict(event), sort_keys=True))


def emit_legal_event(
    event_type: str,
    *,
    document_key: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    metadata: Optional[Mapping[str, Any]] = None,
    sink: AuditSink | None = None,
) -> LegalAuditEvent:
    event = build_event(
        event_type,
        document_key=document_key,
        user_id=user_id,
        tenant_id=tenant_id,
        metadata=metadata,
    )
    (sink or default_audit_sink)(event)
    return event


LEGAL_DOCUMENT_VIEWED = "LEGAL_DOCUMENT_VIEWED"
LEGAL_DOCUMENT_DOWNLOADED = "LEGAL_DOCUMENT_DOWNLOADED"
LEGAL_DOCUMENT_PUBLIC_OPENED = "LEGAL_DOCUMENT_PUBLIC_OPENED"
LEGAL_DOCUMENT_PRINTED = "LEGAL_DOCUMENT_PRINTED"
LEGAL_SEARCH = "LEGAL_SEARCH"
LEGAL_EXPORT = "LEGAL_EXPORT"
LEGAL_PORTAL_OPENED = "LEGAL_PORTAL_OPENED"
LEGAL_ACCESS_DENIED = "LEGAL_ACCESS_DENIED"
