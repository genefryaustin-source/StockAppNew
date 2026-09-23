from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from .legal_permissions import LegalPrincipal, can_manage_legal_portal
from .legal_registry import DOCUMENTS, iter_documents
from .legal_workflow_models import (
    LegalDocumentStatus,
    LegalReviewDecision,
)
from .legal_workflow_service import LegalWorkflowError, LegalWorkflowService


def _select_version(service: LegalWorkflowService):
    versions = service.repository.list_versions()

    if not versions:
        return None

    labels = {
        item.id: (
            f"{DOCUMENTS.get(item.document_key).title if item.document_key in DOCUMENTS else item.document_key}"
            f" · v{item.version} · {item.status.value}"
        )
        for item in versions
    }

    selected_id = st.selectbox(
        "Document version",
        options=list(labels),
        format_func=lambda value: labels[value],
        key="legal_workflow_selected_version",
    )

    return service.repository.get_version(selected_id)


def render_legal_workflow_admin(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
) -> None:
    if not can_manage_legal_portal(principal):
        st.error("Super administrator permission is required.")
        return

    st.markdown("## Legal Review & Publication Workflow")

    summary = service.repository.summary()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Document Versions", summary.total_versions)
    c2.metric("In Review", summary.in_review)
    c3.metric("Published", summary.published)
    c4.metric("Pending Acknowledgements", summary.pending_acknowledgements)

    create_tab, review_tab, publish_tab, acknowledgement_tab, history_tab = st.tabs(
        [
            "Create Version",
            "Review",
            "Publish",
            "Acknowledgements",
            "History",
        ]
    )

    with create_tab:
        with st.form("legal_create_version_form"):
            document_key = st.selectbox(
                "Document",
                options=[document.key for document in iter_documents()],
                format_func=lambda value: DOCUMENTS[value].title,
            )
            version = st.text_input("Version", placeholder="2.0")
            effective_date = st.date_input("Effective date")
            summary_text = st.text_area(
                "Change summary",
                placeholder="Describe the material changes in this version.",
            )
            submitted = st.form_submit_button("Create Draft Version")

        if submitted:
            if not version.strip():
                st.error("Version is required.")
            else:
                record = service.create_version(
                    document_key=document_key,
                    version=version.strip(),
                    effective_date=effective_date.isoformat(),
                    summary=summary_text.strip(),
                    actor_user_id=principal.user_id,
                    tenant_id=principal.tenant_id,
                )
                st.success(f"Created draft version {record.version}.")

    with review_tab:
        selected = _select_version(service)

        if selected is None:
            st.info("Create a document version before starting review.")
        else:
            st.json(asdict(selected))

            if selected.status in {
                LegalDocumentStatus.DRAFT,
                LegalDocumentStatus.CHANGES_REQUESTED,
            }:
                if st.button(
                    "Submit for Review",
                    key="legal_submit_review",
                    use_container_width=True,
                ):
                    try:
                        service.transition(
                            version_id=selected.id,
                            target_status=LegalDocumentStatus.IN_REVIEW,
                            actor_user_id=principal.user_id,
                            tenant_id=principal.tenant_id,
                        )
                        st.success("Version submitted for review.")
                        st.rerun()
                    except LegalWorkflowError as exc:
                        st.error(str(exc))

            if selected.status == LegalDocumentStatus.IN_REVIEW:
                decision = st.selectbox(
                    "Review decision",
                    options=list(LegalReviewDecision),
                    format_func=lambda item: item.value.replace("_", " ").title(),
                )
                comments = st.text_area("Reviewer comments")

                if st.button(
                    "Record Review",
                    key="legal_record_review",
                    use_container_width=True,
                    type="primary",
                ):
                    service.record_review(
                        version_id=selected.id,
                        reviewer_user_id=principal.user_id or "unknown",
                        decision=decision,
                        comments=comments.strip(),
                        tenant_id=principal.tenant_id,
                    )
                    st.success("Review recorded.")
                    st.rerun()

            reviews = service.repository.list_reviews(selected.id)
            if reviews:
                st.markdown("### Review History")
                st.dataframe(
                    [asdict(item) for item in reviews],
                    use_container_width=True,
                    hide_index=True,
                )

    with publish_tab:
        selected = _select_version(service)

        if selected is None:
            st.info("No document versions are available.")
        else:
            st.json(asdict(selected))

            if selected.status == LegalDocumentStatus.APPROVED:
                if st.button(
                    "Publish Version",
                    key="legal_publish_version",
                    use_container_width=True,
                    type="primary",
                ):
                    try:
                        service.transition(
                            version_id=selected.id,
                            target_status=LegalDocumentStatus.PUBLISHED,
                            actor_user_id=principal.user_id,
                            tenant_id=principal.tenant_id,
                        )
                        st.success("Version published.")
                        st.rerun()
                    except LegalWorkflowError as exc:
                        st.error(str(exc))

            if selected.status == LegalDocumentStatus.PUBLISHED:
                if st.button(
                    "Retire Version",
                    key="legal_retire_version",
                    use_container_width=True,
                ):
                    try:
                        service.transition(
                            version_id=selected.id,
                            target_status=LegalDocumentStatus.RETIRED,
                            actor_user_id=principal.user_id,
                            tenant_id=principal.tenant_id,
                        )
                        st.warning("Version retired.")
                        st.rerun()
                    except LegalWorkflowError as exc:
                        st.error(str(exc))

    with acknowledgement_tab:
        selected = _select_version(service)

        if selected is None:
            st.info("No document versions are available.")
        elif selected.status != LegalDocumentStatus.PUBLISHED:
            st.info("Only published versions can be assigned for acknowledgement.")
        else:
            recipients = st.text_area(
                "Recipient user IDs",
                placeholder="One user ID per line",
            )
            due_at = st.text_input(
                "Due date/time (optional)",
                placeholder="2026-08-31T23:59:59Z",
            )

            if st.button(
                "Request Acknowledgements",
                key="legal_request_acknowledgements",
                use_container_width=True,
                type="primary",
            ):
                user_ids = [
                    line.strip()
                    for line in recipients.splitlines()
                    if line.strip()
                ]

                if not user_ids:
                    st.error("Enter at least one user ID.")
                else:
                    records = service.request_acknowledgements(
                        document_key=selected.document_key,
                        document_version=selected.version,
                        users=[
                            (user_id, principal.tenant_id)
                            for user_id in user_ids
                        ],
                        due_at=due_at.strip() or None,
                        actor_user_id=principal.user_id,
                        tenant_id=principal.tenant_id,
                    )
                    st.success(
                        f"Created or retained {len(records)} acknowledgement requests."
                    )

            acknowledgements = service.repository.list_acknowledgements(
                document_key=selected.document_key
            )
            if acknowledgements:
                st.dataframe(
                    [asdict(item) for item in acknowledgements],
                    use_container_width=True,
                    hide_index=True,
                )

    with history_tab:
        versions = service.repository.list_versions()
        if versions:
            st.dataframe(
                [asdict(item) for item in versions],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No workflow history is available.")
