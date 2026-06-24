"""
modules/options/options_validation_dashboard.py

Read-only Streamlit dashboard for validating the options stack.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.options.options_validation_engine import (
    run_options_validation,
    validation_frame,
)


def _status_badge(status: str) -> str:
    status = str(status or "").upper()
    if status == "PASS":
        return "✅ PASS"
    if status == "WARN":
        return "⚠️ WARN"
    if status == "FAIL":
        return "❌ FAIL"
    return status


def render_options_validation_dashboard(
    db: Any | None = None,
    tenant_id: str = "tenant_default",
    paper: bool = True,
):
    st.subheader("🧪 Options Validation Center")
    st.caption(
        "Read-only QA checks for provider chain data, Greeks, IV, positions, and order history."
    )

    col_a, col_b, col_c = st.columns([2, 2, 1])

    with col_a:
        ticker = st.text_input(
            "Validation Ticker",
            value="SPY",
            key="options_validation_ticker",
        ).upper().strip()

    with col_b:
        expiration = st.text_input(
            "Optional Expiration",
            value="",
            placeholder="YYYY-MM-DD",
            key="options_validation_expiration",
        ).strip() or None

    with col_c:
        run_clicked = st.button(
            "Run Validation",
            key="options_validation_run",
            type="primary",
            use_container_width=True,
        )

    if run_clicked:
        with st.spinner("Running options validation checks..."):
            st.session_state["options_validation_result"] = run_options_validation(
                ticker=ticker,
                expiration=expiration,
                paper=paper,
                db=db,
                tenant_id=tenant_id,
            )

    result = st.session_state.get("options_validation_result")

    if not result:
        st.info("Click **Run Validation** to begin.")
        return

    totals = result.get("totals", {}) or {}

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pass", totals.get("PASS", 0))
    m2.metric("Warnings", totals.get("WARN", 0))
    m3.metric("Failures", totals.get("FAIL", 0))
    m4.metric("Provider", result.get("provider") or result.get("source") or "unknown")

    df = validation_frame(result)

    if df.empty:
        st.warning("No validation rows returned.")
        return

    df_display = df.copy()
    if "status" in df_display.columns:
        df_display["status"] = df_display["status"].apply(_status_badge)

    st.markdown("### Validation Results")
    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
    )

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
        st.error("Failures detected. Review failed checks before relying on downstream options analytics.")
        st.dataframe(failures, use_container_width=True, hide_index=True)

    if not warnings.empty:
        st.warning("Warnings detected. These may be acceptable depending on provider coverage, but should be reviewed.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)

    with st.expander("Raw Validation Payload", expanded=False):
        st.json(result)
