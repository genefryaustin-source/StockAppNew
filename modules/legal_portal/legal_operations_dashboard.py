from __future__ import annotations

from dataclasses import asdict

import streamlit as st

from .legal_escalation_models import LegalOverrideReason
from .legal_evidence import (
    build_evidence_package,
    evidence_package_json,
)
from .legal_override_service import (
    LegalOverrideService,
    get_legal_override_service,
)
from .legal_permissions import (
    LegalPrincipal,
    can_manage_legal_portal,
)
from .legal_workflow_service import LegalWorkflowService


def render_legal_operations_dashboard(
    *,
    principal: LegalPrincipal,
    workflow_service: LegalWorkflowService,
    override_service: LegalOverrideService | None = None,
) -> None:
    if not can_manage_legal_portal(principal):
        st.error("Super administrator permission is required.")
        return

    override_service = (
        override_service
        or get_legal_override_service()
    )

    st.markdown("## Legal Operations Control")

    override_tab, evidence_tab, retention_tab = st.tabs(
        [
            "Access Overrides",
            "Evidence Packages",
            "Retention Policy",
        ]
    )

    with override_tab:
        with st.form("legal_override_create_form"):
            user_id = st.text_input("Target user ID")
            tenant_id = st.text_input(
                "Tenant ID",
                value=principal.tenant_id or "",
            )
            acknowledgement_id = st.text_input(
                "Acknowledgement ID (optional)",
            )
            document_key = st.text_input(
                "Document key (optional)",
            )
            reason = st.selectbox(
                "Reason",
                options=list(LegalOverrideReason),
                format_func=lambda item: item.value.replace("_", " ").title(),
            )
            justification = st.text_area("Justification")
            expires_at = st.text_input(
                "Expires at (optional UTC ISO timestamp)",
                placeholder="2026-08-31T23:59:59Z",
            )
            submitted = st.form_submit_button("Create Override")

        if submitted:
            if not user_id.strip():
                st.error("Target user ID is required.")
            else:
                try:
                    record = override_service.create_override(
                        user_id=user_id.strip(),
                        tenant_id=tenant_id.strip() or None,
                        acknowledgement_id=(
                            acknowledgement_id.strip() or None
                        ),
                        document_key=document_key.strip() or None,
                        reason=reason,
                        justification=justification,
                        created_by=principal.user_id or "unknown",
                        expires_at=expires_at.strip() or None,
                    )
                    st.success(f"Created override {record.id}.")
                except ValueError as exc:
                    st.error(str(exc))

        records = override_service.repository.list()

        if records:
            st.dataframe(
                [asdict(item) for item in records],
                use_container_width=True,
                hide_index=True,
            )

            active_ids = [
                item.id
                for item in records
                if item.revoked_at is None
            ]

            if active_ids:
                selected = st.selectbox(
                    "Override to revoke",
                    active_ids,
                )

                if st.button(
                    "Revoke Override",
                    use_container_width=True,
                ):
                    override_service.revoke_override(
                        override_id=selected,
                        revoked_by=principal.user_id or "unknown",
                        tenant_id=principal.tenant_id,
                    )
                    st.warning("Override revoked.")
                    st.rerun()
        else:
            st.info("No legal access overrides have been recorded.")

    with evidence_tab:
        user_filter = st.text_input(
            "Evidence user ID (optional)",
            key="legal_evidence_user",
        )
        tenant_filter = st.text_input(
            "Evidence tenant ID (optional)",
            value=principal.tenant_id or "",
            key="legal_evidence_tenant",
        )
        document_filter = st.text_input(
            "Evidence document key (optional)",
            key="legal_evidence_document",
        )

        package = build_evidence_package(
            service=workflow_service,
            generated_by=principal.user_id or "unknown",
            user_id=user_filter.strip() or None,
            tenant_id=tenant_filter.strip() or None,
            document_key=document_filter.strip() or None,
        )

        st.download_button(
            "Download Evidence Package",
            data=evidence_package_json(package),
            file_name="legal-evidence-package.json",
            mime="application/json",
            use_container_width=True,
        )

        st.json(package.payload)

    with retention_tab:
        from .legal_retention import DEFAULT_RETENTION_RULES

        st.dataframe(
            [
                {
                    "retention_class": rule.retention_class.value,
                    "retain_days": rule.retain_days,
                    "description": rule.description,
                }
                for rule in DEFAULT_RETENTION_RULES
            ],
            use_container_width=True,
            hide_index=True,
        )

        st.warning(
            "Retention periods are configuration defaults and require "
            "approval by legal counsel and records-management stakeholders."
        )
