from __future__ import annotations
from dataclasses import dataclass
from html import escape
from typing import Optional, Sequence
import streamlit as st

@dataclass(frozen=True)
class MetadataItem:
    label: str
    value: str

@dataclass(frozen=True)
class RelatedDocument:
    key: str
    title: str
    summary: str

def render_metadata_panel(items: Sequence[MetadataItem], counsel_review_required: bool = False) -> None:
    cells = "".join(
        f'<div class="aiq-legal-metadata-cell"><span class="aiq-legal-metadata-label">{escape(i.label)}</span>'
        f'<span class="aiq-legal-metadata-value">{escape(i.value)}</span></div>'
        for i in items
    )
    if counsel_review_required:
        cells += (
            '<div class="aiq-legal-metadata-cell aiq-legal-metadata-review">'
            '<span class="aiq-legal-metadata-label">Publication status</span>'
            '<span class="aiq-legal-metadata-value">Counsel review required</span></div>'
        )
    st.markdown(f'<section class="aiq-legal-metadata-grid">{cells}</section>', unsafe_allow_html=True)

def render_callout(title: str, body: str, kind: str = "info") -> None:
    allowed = {"info","success","warning","danger"}
    kind = kind if kind in allowed else "info"
    icon = {"info":"ℹ","success":"✓","warning":"⚠","danger":"!"}[kind]
    st.markdown(
        f'<aside class="aiq-legal-callout aiq-legal-callout--{kind}">'
        f'<div class="aiq-legal-callout-icon">{icon}</div><div>'
        f'<div class="aiq-legal-callout-title">{escape(title)}</div>'
        f'<div class="aiq-legal-callout-body">{body}</div></div></aside>',
        unsafe_allow_html=True,
    )

def render_document_card(key: str, title: str, summary: str, category: str, version: str, status: str = "Available") -> bool:
    status_class = "success" if status.lower() == "available" else "warning"
    st.markdown(
        f'<article class="aiq-legal-document-card">'
        f'<div class="aiq-legal-document-card-topline"><span class="aiq-legal-document-category">{escape(category)}</span>'
        f'<span class="aiq-legal-status-badge aiq-legal-status-badge--{status_class}">{escape(status)}</span></div>'
        f'<h3>{escape(title)}</h3><p>{escape(summary)}</p>'
        f'<div class="aiq-legal-document-card-footer">Version {escape(version)}</div></article>',
        unsafe_allow_html=True,
    )
    return st.button(f"Open {title}", key=f"legal_card_component_{key}", use_container_width=True)

def render_related_documents(documents: Sequence[RelatedDocument]) -> None:
    if not documents:
        return
    st.subheader("Related Documents")
    cols = st.columns(min(3, len(documents)))
    for idx, doc in enumerate(documents):
        with cols[idx % len(cols)]:
            st.markdown(
                f'<article class="aiq-legal-related-card"><h3>{escape(doc.title)}</h3>'
                f'<p>{escape(doc.summary)}</p></article>',
                unsafe_allow_html=True,
            )
            if st.button(f"Open {doc.title}", key=f"legal_related_{doc.key}", use_container_width=True):
                st.query_params["legal_document"] = doc.key
                st.rerun()

def render_action_bar(filename: str, html_data: str, public_path: Optional[str]) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Download HTML", data=html_data, file_name=filename, mime="text/html", use_container_width=True)
    with c2:
        if public_path:
            st.link_button("Open Public Version", public_path, use_container_width=True)
        else:
            st.button("Public Version Unavailable", disabled=True, use_container_width=True)
    with c3:
        st.markdown('<button class="aiq-legal-native-button" onclick="window.print()">Print Document</button>', unsafe_allow_html=True)

def render_empty_state(title: str, message: str) -> None:
    st.markdown(
        f'<section class="aiq-legal-empty-state"><div class="aiq-legal-empty-icon">⌕</div>'
        f'<h3>{escape(title)}</h3><p>{escape(message)}</p></section>',
        unsafe_allow_html=True,
    )
