from __future__ import annotations

import streamlit as st

from .legal_permissions import LegalPrincipal
from .legal_workflow_models import AcknowledgementStatus
from .legal_workflow_service import LegalWorkflowService


def render_acknowledgement_banner(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
) -> None:
    if not principal.authenticated or not principal.user_id:
        return

    pending = [
        item
        for item in service.repository.list_acknowledgements(
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
        )
        if item.status == AcknowledgementStatus.PENDING
    ]

    if not pending:
        return

    st.warning(
        f"You have {len(pending)} pending legal acknowledgement"
        f"{'s' if len(pending) != 1 else ''}. "
        "Open Legal Acknowledgements to review and respond."
    )
