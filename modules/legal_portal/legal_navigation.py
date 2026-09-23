from __future__ import annotations

import streamlit as st

from .legal_registry import categories, iter_documents


def render_legal_sidebar(current_key: str) -> str:
    st.sidebar.markdown("### Legal & Compliance")
    st.sidebar.caption("AIQ Intellus Enterprise Legal Portal")

    selected = current_key

    for category in categories():
        with st.sidebar.expander(category, expanded=True):
            for document in iter_documents(category):
                label = f"• {document.title}"
                if st.button(
                    label,
                    key=f"legal_nav_{document.key}",
                    use_container_width=True,
                    type="primary" if document.key == current_key else "secondary",
                ):
                    selected = document.key
                    st.query_params["legal_document"] = document.key
                    st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Return to Application", use_container_width=True):
        st.query_params.clear()
        st.session_state.pop("legal_portal_active", None)
        st.rerun()

    return selected
