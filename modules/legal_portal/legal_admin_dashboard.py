from __future__ import annotations

import streamlit as st

from .legal_health import check_legal_health
from .legal_permissions import LegalPrincipal, can_view_health
from .legal_registry import iter_documents
from .legal_version import get_portal_version


def render_legal_admin_dashboard(principal: LegalPrincipal) -> None:
    if not can_view_health(principal):
        st.error("You do not have permission to view Legal Portal health.")
        return

    health = check_legal_health()
    version = get_portal_version(document_count=health.total_documents)

    st.markdown("## Legal Portal Operations")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Status", health.status.title())
    c2.metric("Registered Documents", health.total_documents)
    c3.metric("Available Documents", health.available_documents)
    c4.metric("Missing Documents", len(health.missing_documents))

    st.markdown("### Build")
    st.json(
        {
            "portal_version": version.portal_version,
            "build_date": version.build_date,
            "git_commit": version.git_commit,
            "git_branch": version.git_branch,
            "environment": version.environment,
        }
    )

    st.markdown("### Document Inventory")
    rows = [
        {
            "key": document.key,
            "title": document.title,
            "category": document.category,
            "version": document.version,
            "effective_date": document.effective_date,
            "source_exists": document.source_path.exists(),
            "public_path": document.public_path,
        }
        for document in iter_documents()
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if health.missing_documents:
        st.warning("Missing legal source files")
        st.code("\n".join(health.missing_documents), language="text")
