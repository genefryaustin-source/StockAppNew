from __future__ import annotations

from html import escape
import streamlit as st

from .legal_accessibility import estimate_reading_minutes, render_accessibility_status, render_skip_links
from .legal_components import (
    MetadataItem,
    render_callout,
    render_document_card,
    render_metadata_panel,
    render_related_documents,
)
from .legal_document_loader import LegalDocumentLoadError, load_document, plain_text
from .legal_export import render_export_panel
from .legal_navigation import render_legal_sidebar
from .legal_preferences import render_preferences_panel
from .legal_registry import get_document, iter_documents
from .legal_relations import related_documents
from .legal_search_ui import render_search_panel
from .legal_shortcuts import render_shortcut_bridge, render_shortcut_help
from .legal_styles import load_legal_styles
from .legal_theme import apply_legal_preferences
from .legal_health import check_legal_health, render_health_panel
from .legal_audit import LEGAL_ACCESS_DENIED, LEGAL_DOCUMENT_VIEWED, LEGAL_PORTAL_OPENED, emit_legal_event
from .legal_permissions import can_view_document, principal_from_user
from .legal_version import get_portal_version, render_version_panel

def _query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)

def _render_header(document) -> None:
    st.markdown(
        f"""
        <section class="aiq-legal-shell">
            <div class="aiq-legal-kicker">AIQ Intellus Legal &amp; Compliance</div>
            <h1 class="aiq-legal-title">{escape(document.title)}</h1>
            <p class="aiq-legal-subtitle">{escape(document.summary)}</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    render_metadata_panel(
        [
            MetadataItem("Version", document.version),
            MetadataItem("Effective date", document.effective_date),
            MetadataItem("Category", document.category),
        ],
        counsel_review_required=document.requires_counsel_review,
    )

def _render_library() -> None:
    st.subheader("Document Library")
    documents = list(iter_documents())
    for start in range(0, len(documents), 3):
        columns = st.columns(3)
        for column, document in zip(columns, documents[start:start + 3]):
            with column:
                if render_document_card(
                    document.key,
                    document.title,
                    document.summary,
                    document.category,
                    document.version,
                    "Available" if document.source_path.exists() else "Pending",
                ):
                    st.query_params["legal_document"] = document.key
                    st.rerun()

def _render_document(document) -> None:
    try:
        html = load_document(document)
        text = plain_text(document)
    except LegalDocumentLoadError as exc:
        st.error(str(exc))
        return

    render_accessibility_status(
        document_title=document.title,
        estimated_minutes=estimate_reading_minutes(text),
    )

    if document.requires_counsel_review:
        render_callout(
            "Legal review required",
            "This production-oriented draft must be reviewed and approved by qualified legal counsel before public launch.",
            kind="warning",
        )

    st.markdown(
        f'<div id="aiq-legal-main" class="aiq-legal-doc">{html}</div>',
        unsafe_allow_html=True,
    )
    st.divider()
    render_export_panel(document, html, document.public_path)
    render_related_documents(related_documents(document.key))

def render_legal_portal(*, default_document: str = "privacy-policy", current_user=None, audit_sink=None) -> None:
    load_legal_styles()
    render_skip_links()
    render_shortcut_bridge()
    st.session_state["legal_portal_active"] = True

    principal = principal_from_user(current_user)
    requested = _query_value("legal_document", default_document)
    current = get_document(requested)

    emit_legal_event(
        LEGAL_PORTAL_OPENED,
        document_key=current.key,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        sink=audit_sink,
    )

    if not can_view_document(principal, current.key):
        emit_legal_event(
            LEGAL_ACCESS_DENIED,
            document_key=current.key,
            user_id=principal.user_id,
            tenant_id=principal.tenant_id,
            sink=audit_sink,
        )
        st.error("You do not have permission to view this legal document.")
        st.stop()

    emit_legal_event(
        LEGAL_DOCUMENT_VIEWED,
        document_key=current.key,
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        sink=audit_sink,
    )

    render_legal_sidebar(current.key)
    preferences = render_preferences_panel()
    apply_legal_preferences(preferences)
    render_shortcut_help()
    health = check_legal_health()
    version = get_portal_version(document_count=health.total_documents)
    render_health_panel(health)
    render_version_panel(version)

    _render_header(current)
    render_search_panel(expanded=False)

    document_tab, library_tab = st.tabs(["Document", "Document Library"])
    with document_tab:
        _render_document(current)
    with library_tab:
        _render_library()
