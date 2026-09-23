from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .legal_compliance_service import (
    calculate_metrics,
    send_overdue_notifications,
)
from .legal_notifications import NotificationSink
from .legal_workflow_service import LegalWorkflowService


@dataclass(frozen=True)
class LegalComplianceJobResult:
    ran_at: str
    total_assignments: int
    overdue_assignments: int
    notifications_sent: int


def run_legal_compliance_job(
    *,
    service: LegalWorkflowService,
    tenant_id: str | None = None,
    user_email_resolver: Callable[[str], str | None] | None = None,
    notification_sink: NotificationSink | None = None,
) -> LegalComplianceJobResult:
    acknowledgements = service.repository.list_acknowledgements(
        tenant_id=tenant_id,
    )
    metrics = calculate_metrics(acknowledgements)

    notifications_sent = send_overdue_notifications(
        service=service,
        user_email_resolver=user_email_resolver,
        notification_sink=notification_sink,
        tenant_id=tenant_id,
    )

    return LegalComplianceJobResult(
        ran_at=datetime.now(timezone.utc).isoformat(),
        total_assignments=metrics.total_assignments,
        overdue_assignments=metrics.overdue,
        notifications_sent=notifications_sent,
    )
