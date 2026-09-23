from __future__ import annotations

from html import escape
from typing import Iterable

import streamlit as st

from .legal_router import open_legal_document


LOGIN_DOCUMENTS = (
    ("privacy-policy", "Privacy Policy"),
    ("terms-of-service", "Terms of Service"),
    ("cookie-policy", "Cookie Policy"),
    ("financial-disclaimer", "Financial Disclaimer"),
    ("risk-disclosure", "Risk Disclosure"),
)

FOOTER_DOCUMENTS = (
    ("privacy-policy", "Privacy"),
    ("terms-of-service", "Terms"),
    ("cookie-policy", "Cookies"),
    ("risk-disclosure", "Risk"),
    ("ai-disclosure", "AI Disclosure"),
    ("security", "Security"),
    ("contact", "Contact"),
)


def legal_query_url(document_key: str) -> str:
    return f"/?page=legal&legal_document={document_key}"


def render_login_legal_links() -> None:
    links = " &nbsp;|&nbsp; ".join(
        f'<a href="{legal_query_url(key)}" target="_self">{escape(label)}</a>'
        for key, label in LOGIN_DOCUMENTS
    )

    st.markdown(
        f'''
        <div class="aiq-login-legal-links">
            {links}
        </div>
        ''',
        unsafe_allow_html=True,
    )


def render_application_legal_footer(
    *,
    build_version: str | None = None,
    git_commit: str | None = None,
) -> None:
    links = " &nbsp;|&nbsp; ".join(
        f'<a href="{legal_query_url(key)}" target="_self">{escape(label)}</a>'
        for key, label in FOOTER_DOCUMENTS
    )

    build_parts = []
    if build_version:
        build_parts.append(f"Build {escape(build_version)}")
    if git_commit:
        build_parts.append(f"Git {escape(git_commit)}")

    build_line = " &nbsp;•&nbsp; ".join(build_parts)

    st.markdown(
        f'''
        <footer class="aiq-application-legal-footer">
            <div>{links}</div>
            <div class="aiq-application-legal-footer-copy">
                © 2026 Conduro Ventures LLC
                {f"<br>{build_line}" if build_line else ""}
            </div>
        </footer>
        ''',
        unsafe_allow_html=True,
    )
