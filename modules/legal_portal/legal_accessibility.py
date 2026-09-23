from __future__ import annotations

from html import escape
from typing import Optional
import streamlit as st

def render_skip_links() -> None:
    st.markdown(
        """
        <nav class="aiq-legal-skip-links" aria-label="Skip navigation">
            <a href="#aiq-legal-main">Skip to legal document</a>
            <a href="#aiq-legal-actions">Skip to document actions</a>
        </nav>
        """,
        unsafe_allow_html=True,
    )

def estimate_reading_minutes(plain_text: str, words_per_minute: int = 210) -> int:
    words = len((plain_text or "").split())
    return max(1, round(words / max(words_per_minute, 1)))

def render_accessibility_status(
    document_title: str,
    estimated_minutes: Optional[int] = None,
) -> None:
    reading = f"{estimated_minutes} minute estimated read" if estimated_minutes else "Reading time varies"
    st.markdown(
        f"""
        <section class="aiq-legal-accessibility-status"
                 aria-label="Document accessibility information">
            <span><strong>Document:</strong> {escape(document_title)}</span>
            <span><strong>Language:</strong> English</span>
            <span><strong>Reading time:</strong> {escape(reading)}</span>
        </section>
        """,
        unsafe_allow_html=True,
    )
