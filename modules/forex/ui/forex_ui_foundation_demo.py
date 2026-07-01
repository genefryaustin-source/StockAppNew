"""
modules/forex/ui/forex_ui_foundation_demo.py

Small demo for Phase 22.1 foundation components.
"""

from __future__ import annotations


def render_forex_ui_foundation_demo():
    import streamlit as st

    from modules.forex.ui.forex_ui_layout import (
        render_page_header,
        render_section_header,
        panel,
    )
    from modules.forex.ui.forex_ui_status import render_status_pill, render_health_pill

    render_page_header(
        "Forex UI Foundation",
        "Shared institutional theme, layout, and status components.",
        icon="🎛️",
    )

    cols = st.columns(5)
    statuses = ["READY", "ACTIVE", "WARNING", "ERROR", "DISABLED"]
    for col, status in zip(cols, statuses):
        with col:
            render_status_pill(status)

    with panel("Institutional Panel", kicker="Demo", meta="Phase 22.1"):
        st.write("This panel uses the shared Forex UI framework.")
        render_health_pill({"status": "HEALTHY"}, label="Provider")
        render_section_header("Nested Section", kicker="Component")
        st.caption("Next phases will add cards, metrics, tables, charts, and heatmaps.")
