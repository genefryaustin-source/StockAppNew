from __future__ import annotations

import streamlit as st
from .legal_preferences import LegalPreferences

def apply_legal_preferences(preferences: LegalPreferences) -> None:
    scale = preferences.text_scale / 100
    classes = " ".join(
        value for value in [
            preferences.theme,
            "high-contrast" if preferences.high_contrast else "",
            "reduced-motion" if preferences.reduced_motion else "",
            "wide-reading" if preferences.wide_reading else "",
        ] if value
    )

    css = """
    <style>
    :root{{--aiq-legal-text-scale:{scale:.2f};}}
    .aiq-legal-doc{{font-size:calc(1rem * var(--aiq-legal-text-scale));}}
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-shell,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-doc,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-metadata-cell,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-search-card,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-document-card,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-related-card{{
        background:#f8fafc!important;color:#0f172a!important;border-color:rgba(15,23,42,.16)!important;
    }}
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-doc *,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-shell *,
    body:has(.aiq-legal-theme-marker.light) .aiq-legal-metadata-cell *{{
        color:#0f172a!important;
    }}
    body:has(.aiq-legal-theme-marker.high-contrast) .aiq-legal-doc,
    body:has(.aiq-legal-theme-marker.high-contrast) .aiq-legal-shell,
    body:has(.aiq-legal-theme-marker.high-contrast) .aiq-legal-metadata-cell{{
        border-width:2px!important;border-color:#67E8F9!important;
    }}
    body:has(.aiq-legal-theme-marker.wide-reading) .aiq-legal-doc{{max-width:none!important;}}
    body:has(.aiq-legal-theme-marker.reduced-motion) *,
    body:has(.aiq-legal-theme-marker.reduced-motion) *::before,
    body:has(.aiq-legal-theme-marker.reduced-motion) *::after{{
        animation-duration:.001ms!important;animation-iteration-count:1!important;
        scroll-behavior:auto!important;transition-duration:.001ms!important;
    }}
    @media(prefers-color-scheme:light){{
        body:has(.aiq-legal-theme-marker.system) .aiq-legal-shell,
        body:has(.aiq-legal-theme-marker.system) .aiq-legal-doc,
        body:has(.aiq-legal-theme-marker.system) .aiq-legal-metadata-cell{{
            background:#f8fafc!important;color:#0f172a!important;
        }}
    }}
    </style>
    <div class="aiq-legal-theme-marker {classes}" aria-hidden="true"></div>
    """.format(scale=scale, classes=classes)

    st.markdown(css, unsafe_allow_html=True)
