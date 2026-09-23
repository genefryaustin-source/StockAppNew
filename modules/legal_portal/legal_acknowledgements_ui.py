from __future__ import annotations

import streamlit as st

from .legal_permissions import LegalPrincipal
from .legal_registry import get_document
from .legal_workflow_models import AcknowledgementStatus
from .legal_workflow_service import LegalWorkflowError, LegalWorkflowService


def render_user_acknowledgements(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
) -> None:
    st.markdown("## Required Legal Acknowledgements")

    if not principal.authenticated or not principal.user_id:
        st.info("Sign in to view legal acknowledgement requirements.")
        return

    records = service.repository.list_acknowledgements(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
    )

    if not records:
        st.success("You have no pending legal acknowledgements.")
        return

    pending = [
        item
        for item in records
        if item.status == AcknowledgementStatus.PENDING
    ]

    if not pending:
        st.success("All assigned legal documents have been acknowledged.")

    for record in records:
        document = get_document(record.document_key)

        with st.container(border=True):
            st.markdown(f"### {document.title}")
            st.caption(
                f"Version {record.document_version} · "
                f"Status: {record.status.value.replace('_', ' ').title()}"
            )

            if record.due_at:
                st.caption(f"Due: {record.due_at}")

            st.write(document.summary)

            if record.status != AcknowledgementStatus.PENDING:
                continue

            accepted = st.checkbox(
                "I confirm that I have reviewed this document.",
                key=f"legal_ack_checkbox_{record.id}",
            )

            accept_col, decline_col = st.columns(2)

            with accept_col:
                if st.button(
                    "Accept",
                    key=f"legal_ack_accept_{record.id}",
                    disabled=not accepted,
                    use_container_width=True,
                    type="primary",
                ):
                    try:
                        service.respond_to_acknowledgement(
                            acknowledgement_id=record.id,
                            status=AcknowledgementStatus.ACCEPTED,
                            user_id=principal.user_id,
                            tenant_id=principal.tenant_id,
                        )
                        st.success("Acknowledgement recorded.")
                        st.rerun()
                    except LegalWorkflowError as exc:
                        st.error(str(exc))

            with decline_col:
                if st.button(
                    "Decline",
                    key=f"legal_ack_decline_{record.id}",
                    use_container_width=True,
                ):
                    try:
                        service.respond_to_acknowledgement(
                            acknowledgement_id=record.id,
                            status=AcknowledgementStatus.DECLINED,
                            user_id=principal.user_id,
                            tenant_id=principal.tenant_id,
                        )
                        st.warning("Decline response recorded.")
                        st.rerun()
                    except LegalWorkflowError as exc:
                        st.error(str(exc))
