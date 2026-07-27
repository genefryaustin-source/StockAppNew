"""
modules/options/options_liquidity_validation_dashboard.py

Streamlit dashboard for options liquidity validation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_liquidity_validation_engine import (
    liquidity_audit_frame,
    run_liquidity_validation,
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


def render_options_liquidity_validation_dashboard():
    st.subheader("💧 Liquidity Validation")
    st.caption(
        "Validates bid/ask quality, spreads, volume, open interest, and tradability. Read-only."
    )

    c1, c2, c3 = st.columns([2, 2, 1])

    with c1:
        ticker = st.text_input(
            "Ticker",
            value="SPY",
            key="liq_validation_ticker",
        ).upper().strip()

    with c2:
        expiration = st.text_input(
            "Optional Expiration",
            value="",
            placeholder="YYYY-MM-DD",
            key="liq_validation_expiration",
        ).strip() or None

    with c3:
        run_clicked = st.button(
            "Run Liquidity Audit",
            key="liq_validation_run",
            type="primary",
            use_container_width=True,
        )

    if run_clicked:
        with st.spinner("Running liquidity validation..."):
            st.session_state["options_liquidity_validation_result"] = run_liquidity_validation(
                ticker=ticker,
                expiration=expiration,
            )

    result = st.session_state.get("options_liquidity_validation_result")
    if not result:
        st.info("Click **Run Liquidity Audit** to begin.")
        return

    totals = result.get("totals", {}) or {}

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Grade", result.get("grade", "—"))
    m2.metric("Pass", totals.get("PASS", 0))
    m3.metric("Warnings", totals.get("WARN", 0))
    m4.metric("Failures", totals.get("FAIL", 0))
    m5.metric("Rows", result.get("rows_available", 0))
    m6.metric("Provider", result.get("provider") or result.get("source") or "unknown")

    df = liquidity_audit_frame(result)

    if df.empty:
        st.warning("No liquidity validation rows returned.")
        with st.expander("Raw Payload", expanded=False):
            st.json(result)
        return

    display = df.copy()
    if "status" in display.columns:
        display["status"] = display["status"].apply(_badge)

    st.markdown("### Liquidity Validation Results")
    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown("### Status Summary")
    if "status" in df.columns:
        summary = df["status"].value_counts().reset_index()
        summary.columns = ["status", "count"]
        st.dataframe(summary, use_container_width=True, hide_index=True)

    failures = df[df["status"] == "FAIL"] if "status" in df.columns else pd.DataFrame()
    warnings = df[df["status"] == "WARN"] if "status" in df.columns else pd.DataFrame()

    if not failures.empty:
        st.error("Liquidity validation failures detected.")
        st.dataframe(failures, use_container_width=True, hide_index=True)

    if not warnings.empty:
        st.warning("Liquidity validation warnings detected. Review spreads, zero bids, volume, and open interest.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)

    by_expiry = result.get("by_expiry", []) or []
    by_side = result.get("by_side", []) or []
    atm_sample = result.get("atm_sample", []) or []

    st.markdown("### Liquidity by Expiry")
    if by_expiry:
        st.dataframe(pd.DataFrame(by_expiry), use_container_width=True, hide_index=True)
    else:
        st.caption("No expiry summary available.")

    st.markdown("### Liquidity by Side")
    if by_side:
        st.dataframe(pd.DataFrame(by_side), use_container_width=True, hide_index=True)
    else:
        st.caption("No side summary available.")

    with st.expander("ATM Liquidity Sample", expanded=False):
        if atm_sample:
            st.dataframe(pd.DataFrame(atm_sample), use_container_width=True, hide_index=True)
        else:
            st.caption("No ATM sample available.")

    with st.expander("Raw Liquidity Payload", expanded=False):
        st.json(result)
