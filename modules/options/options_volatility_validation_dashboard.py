"""
modules/options/options_volatility_validation_dashboard.py

Streamlit dashboard for options volatility validation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_volatility_validation_engine import (
    run_volatility_validation,
    volatility_audit_frame,
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


def render_options_volatility_validation_dashboard():
    st.subheader("🌊 Volatility Validation")
    st.caption(
        "Validates IV availability, skew, smile continuity, term structure, and ATM IV quality. Read-only."
    )

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        ticker = st.text_input(
            "Ticker",
            value="SPY",
            key="vol_validation_ticker",
        ).upper().strip()

    with c2:
        expiration = st.text_input(
            "Optional Expiration",
            value="",
            placeholder="YYYY-MM-DD",
            key="vol_validation_expiration",
        ).strip() or None

    with c3:
        run_clicked = st.button(
            "Run Vol Audit",
            key="vol_validation_run",
            type="primary",
            use_container_width=True,
        )

    if run_clicked:
        with st.spinner("Running volatility validation..."):
            st.session_state["options_volatility_validation_result"] = run_volatility_validation(
                ticker=ticker,
                expiration=expiration,
            )

    result = st.session_state.get("options_volatility_validation_result")
    if not result:
        st.info("Click **Run Vol Audit** to begin.")
        return

    totals = result.get("totals", {}) or {}

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Pass", totals.get("PASS", 0))
    m2.metric("Warnings", totals.get("WARN", 0))
    m3.metric("Failures", totals.get("FAIL", 0))
    m4.metric("Rows", result.get("rows_available", 0))
    m5.metric("Provider", result.get("provider") or result.get("source") or "unknown")

    df = volatility_audit_frame(result)
    if df.empty:
        st.warning("No volatility validation rows returned.")
        with st.expander("Raw Payload", expanded=False):
            st.json(result)
        return

    display = df.copy()
    if "status" in display.columns:
        display["status"] = display["status"].apply(_badge)

    st.markdown("### Volatility Validation Results")
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### Status Summary")
    if "status" in df.columns:
        summary = df["status"].value_counts().reset_index()
        summary.columns = ["status", "count"]
        st.dataframe(summary, use_container_width=True, hide_index=True)

    fails = df[df["status"] == "FAIL"] if "status" in df.columns else pd.DataFrame()
    warns = df[df["status"] == "WARN"] if "status" in df.columns else pd.DataFrame()

    if not fails.empty:
        st.error("Volatility validation failures detected.")
        st.dataframe(fails, use_container_width=True, hide_index=True)

    if not warns.empty:
        st.warning("Volatility validation warnings detected. Review provider IV quality and edge cases.")
        st.dataframe(warns, use_container_width=True, hide_index=True)

    with st.expander("Surface Sample", expanded=False):
        sample = result.get("surface_sample", []) or []
        if sample:
            st.dataframe(pd.DataFrame(sample), use_container_width=True, hide_index=True)
        else:
            st.caption("No surface sample available.")

    with st.expander("Raw Volatility Payload", expanded=False):
        st.json(result)
