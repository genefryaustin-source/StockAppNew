from __future__ import annotations

from dataclasses import dataclass
import streamlit as st

THEME_KEY = "legal_portal_theme"
CONTRAST_KEY = "legal_portal_high_contrast"
TEXT_SCALE_KEY = "legal_portal_text_scale"
REDUCED_MOTION_KEY = "legal_portal_reduced_motion"
WIDE_READING_KEY = "legal_portal_wide_reading"

@dataclass(frozen=True)
class LegalPreferences:
    theme: str
    high_contrast: bool
    text_scale: int
    reduced_motion: bool
    wide_reading: bool

def render_preferences_panel() -> LegalPreferences:
    with st.expander("Reading & Accessibility", expanded=False):
        theme = st.selectbox(
            "Portal theme",
            options=["dark", "light", "system"],
            format_func=lambda value: value.title(),
            key=THEME_KEY,
        )
        text_scale = st.slider(
            "Legal document text size",
            min_value=90,
            max_value=140,
            step=5,
            key=TEXT_SCALE_KEY,
        )
        left, right = st.columns(2)
        with left:
            high_contrast = st.checkbox("High contrast", key=CONTRAST_KEY)
            reduced_motion = st.checkbox("Reduce motion", key=REDUCED_MOTION_KEY)
        with right:
            wide_reading = st.checkbox("Wider reading column", key=WIDE_READING_KEY)

        if st.button("Reset reading preferences", use_container_width=True):
            st.session_state[THEME_KEY] = "dark"
            st.session_state[CONTRAST_KEY] = False
            st.session_state[TEXT_SCALE_KEY] = 100
            st.session_state[REDUCED_MOTION_KEY] = False
            st.session_state[WIDE_READING_KEY] = False
            st.rerun()

    return LegalPreferences(
        theme=theme,
        high_contrast=high_contrast,
        text_scale=text_scale,
        reduced_motion=reduced_motion,
        wide_reading=wide_reading,
    )
