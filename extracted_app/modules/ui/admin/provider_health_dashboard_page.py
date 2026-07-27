"""
ui/admin/provider_health_dashboard_page.py
"""

from __future__ import annotations

import streamlit as st

from modules.market_data.provider_health_dashboard import (
    render_provider_health_dashboard,
)


def render_provider_health_dashboard_page(
    db,
    user=None,
):
    st.header(
        "Provider Health & Routing"
    )

    render_provider_health_dashboard(
        db=db,
    )