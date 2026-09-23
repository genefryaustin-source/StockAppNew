from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


PAGE_PARAM = "page"
DOCUMENT_PARAM = "legal_document"
LEGAL_PAGE_VALUE = "legal"


@dataclass(frozen=True)
class LegalRoute:
    active: bool
    document_key: str


def _query_value(name: str, default: str = "") -> str:
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return str(value[0]) if value else default
    return str(value)


def resolve_legal_route(default_document: str = "privacy-policy") -> LegalRoute:
    page = _query_value(PAGE_PARAM)
    document_key = _query_value(DOCUMENT_PARAM, default_document)

    active = (
        page.lower() == LEGAL_PAGE_VALUE
        or bool(st.session_state.get("legal_portal_active", False))
    )

    return LegalRoute(active=active, document_key=document_key)


def open_legal_document(document_key: str = "privacy-policy") -> None:
    st.query_params[PAGE_PARAM] = LEGAL_PAGE_VALUE
    st.query_params[DOCUMENT_PARAM] = document_key
    st.session_state["legal_portal_active"] = True
    st.rerun()


def close_legal_portal() -> None:
    if PAGE_PARAM in st.query_params:
        del st.query_params[PAGE_PARAM]
    if DOCUMENT_PARAM in st.query_params:
        del st.query_params[DOCUMENT_PARAM]

    st.session_state.pop("legal_portal_active", None)
    st.rerun()
