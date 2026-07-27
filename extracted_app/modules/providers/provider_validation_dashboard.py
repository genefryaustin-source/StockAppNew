"""
modules/providers/provider_validation_dashboard.py

Streamlit dashboard for provider validation.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.providers.provider_validation_engine import (
    provider_validation_frame,
    run_provider_validation,
)


def _badge(status: str) -> str:
    status = str(status or "").upper()
    if status == "PASS":
        return "✅ PASS"
    if status == "WARN":
        return "⚠️ WARN"
    if status == "FAIL":
        return "❌ FAIL"
    return status


def render_provider_validation_dashboard(db: Any):
    st.subheader("🔌 Provider Validation Center")
    st.caption(
        "Read-only validation for provider telemetry, market data cache, price history feed, and failover readiness."
    )

    run_clicked = st.button(
        "Run Provider Validation",
        key="provider_validation_run",
        type="primary",
    )

    if run_clicked:
        with st.spinner("Running provider validation..."):
            st.session_state["provider_validation_result"] = run_provider_validation(db=db)

    result = st.session_state.get("provider_validation_result")

    if not result:
        st.info("Click **Run Provider Validation** to begin.")
        return

    totals = result.get("totals", {}) or {}
    score = float(result.get("score", 0))
    status = str(result.get("status", "UNKNOWN"))

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Score", f"{score:.2f}%")
    m2.metric("Status", status)
    m3.metric("PASS", totals.get("PASS", 0))
    m4.metric("WARN", totals.get("WARN", 0))
    m5.metric("FAIL", totals.get("FAIL", 0))

    df = provider_validation_frame(result)

    if df.empty:
        st.warning("No provider validation rows returned.")
        with st.expander("Raw Payload", expanded=False):
            st.json(result)
        return

    display = df.copy()
    if "status" in display.columns:
        display["status"] = display["status"].apply(_badge)

    st.markdown("### Validation Results")
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### Results by Category")
    if {"category", "status"}.issubset(df.columns):
        summary = (
            df.groupby(["category", "status"])
            .size()
            .reset_index(name="count")
            .sort_values(["category", "status"])
        )
        st.dataframe(summary, use_container_width=True, hide_index=True)

    failures = df[df["status"].astype(str).str.upper() == "FAIL"] if "status" in df.columns else pd.DataFrame()
    warnings = df[df["status"].astype(str).str.upper() == "WARN"] if "status" in df.columns else pd.DataFrame()

    if not failures.empty:
        st.error("Provider validation failures detected.")
        st.dataframe(failures, use_container_width=True, hide_index=True)

    if not warnings.empty:
        st.warning("Provider validation warnings detected.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)

    with st.expander("Raw Provider Validation Payload", expanded=False):
        st.json(result)
