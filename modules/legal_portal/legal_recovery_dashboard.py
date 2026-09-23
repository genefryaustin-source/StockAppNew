from __future__ import annotations

import streamlit as st

from .legal_backup import build_legal_backup_archive
from .legal_permissions import LegalPrincipal, can_manage_legal_portal
from .legal_workflow_service import LegalWorkflowService


def render_legal_recovery_dashboard(
    *,
    principal: LegalPrincipal,
    service: LegalWorkflowService,
) -> None:
    if not can_manage_legal_portal(principal):
        st.error("Super administrator permission is required.")
        return

    st.markdown("## Legal Backup & Recovery")

    archive = build_legal_backup_archive(
        service=service,
        generated_by=principal.user_id or "unknown",
    )

    st.download_button(
        "Download Legal Backup Archive",
        data=archive,
        file_name="aiq-intellus-legal-backup.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.info(
        "The archive contains a full evidence export and checksum manifest. "
        "Restore automation should be implemented only after the production "
        "database schema and counsel-approved retention rules are finalized."
    )
