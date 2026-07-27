"""
modules/equities_validation_dashboard.py

Streamlit dashboard for equities/stocks platform validation.

Validates:
- prices
- fundamentals
- recommendations
- earnings
- ownership
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.equities_validation_engine import (
    DEFAULT_SYMBOLS,
    equities_validation_frame,
    run_equities_validation,
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


def render_equities_validation_dashboard(
    db: Any,
    tenant_id: str | None = None,
):
    st.subheader("📈 Equities Validation Center")
    st.caption(
        "Read-only validation for stock prices, fundamentals, recommendations, earnings, and ownership data."
    )

    c1, c2 = st.columns([3, 1])

    with c1:
        raw_symbols = st.text_input(
            "Validation Symbols",
            value=", ".join(DEFAULT_SYMBOLS),
            key="equities_validation_symbols",
            help="Comma-separated symbols to test across prices, fundamentals, earnings, and ownership.",
        )

    with c2:
        run_clicked = st.button(
            "Run Validation",
            key="equities_validation_run",
            type="primary",
            use_container_width=True,
        )

    symbols = [
        s.upper().strip()
        for s in raw_symbols.split(",")
        if s.strip()
    ] or DEFAULT_SYMBOLS

    if run_clicked:
        with st.spinner("Running equities validation..."):
            st.session_state["equities_validation_result"] = run_equities_validation(
                db=db,
                tenant_id=tenant_id,
                symbols=symbols,
            )

    result = st.session_state.get("equities_validation_result")

    if not result:
        st.info("Click **Run Validation** to begin.")
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

    df = equities_validation_frame(result)

    if df.empty:
        st.warning("No equities validation rows returned.")
        with st.expander("Raw Payload", expanded=False):
            st.json(result)
        return

    display = df.copy()
    if "status" in display.columns:
        display["status"] = display["status"].apply(_badge)

    st.markdown("### Validation Results")
    st.dataframe(
        display,
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
        st.error("Equities validation failures detected.")
        st.dataframe(failures, use_container_width=True, hide_index=True)

    if not warnings.empty:
        st.warning("Equities validation warnings detected.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)

    with st.expander("Raw Equities Validation Payload", expanded=False):
        st.json(result)
