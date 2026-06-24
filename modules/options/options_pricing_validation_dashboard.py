"""
modules/options/options_pricing_validation_dashboard.py

Streamlit dashboard for independent options pricing validation.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_pricing_validation_engine import (
    DEFAULT_DIVIDEND_YIELD,
    DEFAULT_RISK_FREE_RATE,
    pricing_audit_frame,
    run_pricing_validation,
)


def render_options_pricing_validation_dashboard():
    st.subheader("💵 Options Pricing Validation")
    st.caption(
        "Compares provider mid prices against independent Black-Scholes theoretical values. Read-only."
    )

    c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])

    with c1:
        ticker = st.text_input(
            "Ticker",
            value="SPY",
            key="pricing_validation_ticker",
        ).upper().strip()

    with c2:
        expiration = st.text_input(
            "Optional Expiration",
            value="",
            placeholder="YYYY-MM-DD",
            key="pricing_validation_expiration",
        ).strip() or None

    with c3:
        max_rows = st.number_input(
            "Max Rows",
            min_value=25,
            max_value=1000,
            value=250,
            step=25,
            key="pricing_validation_max_rows",
        )

    with c4:
        run_clicked = st.button(
            "Run Pricing Audit",
            key="pricing_validation_run",
            type="primary",
            use_container_width=True,
        )

    with st.expander("Advanced Inputs", expanded=False):
        rfr = st.number_input(
            "Risk-Free Rate",
            min_value=0.0,
            max_value=0.20,
            value=float(DEFAULT_RISK_FREE_RATE),
            step=0.001,
            format="%.4f",
            key="pricing_validation_rfr",
        )

        div_yield = st.number_input(
            "Dividend Yield",
            min_value=0.0,
            max_value=0.20,
            value=float(DEFAULT_DIVIDEND_YIELD),
            step=0.001,
            format="%.4f",
            key="pricing_validation_div_yield",
        )

    if run_clicked:
        with st.spinner("Running independent pricing audit..."):
            st.session_state["options_pricing_validation_result"] = run_pricing_validation(
                ticker=ticker,
                expiration=expiration,
                max_rows=int(max_rows),
                risk_free_rate=float(rfr),
                dividend_yield=float(div_yield),
            )

    result = st.session_state.get("options_pricing_validation_result")
    if not result:
        st.info("Click **Run Pricing Audit** to begin.")
        return

    totals = result.get("totals", {}) or {}

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Pass", totals.get("PASS", 0))
    m2.metric("Warnings", totals.get("WARN", 0))
    m3.metric("Failures", totals.get("FAIL", 0))
    m4.metric("Rows Audited", result.get("rows_audited", 0))
    m5.metric("Provider", result.get("provider") or result.get("source") or "unknown")

    for note in result.get("notes", []) or []:
        st.warning(note)

    df = pricing_audit_frame(result)
    if df.empty:
        st.warning("No pricing audit rows returned.")
        with st.expander("Raw Payload", expanded=False):
            st.json(result)
        return

    display_cols = [
        "status",
        "option_symbol",
        "option_type",
        "strike",
        "dte",
        "underlying_price",
        "iv",
        "bid",
        "ask",
        "mid",
        "theoretical_value",
        "intrinsic_value",
        "extrinsic_value",
        "price_diff",
        "price_diff_pct",
        "spread",
        "spread_pct",
        "message",
    ]
    display_cols = [c for c in display_cols if c in df.columns]

    st.markdown("### Pricing Audit Results")
    st.dataframe(
        df[display_cols],
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
        st.error("Failures detected in provider pricing compared with theoretical values.")
        st.dataframe(fails[display_cols], use_container_width=True, hide_index=True)

    if not warns.empty:
        st.warning("Warnings detected. Review spread, IV, and provider methodology.")
        st.dataframe(warns[display_cols], use_container_width=True, hide_index=True)

    with st.expander("Raw Pricing Audit Payload", expanded=False):
        st.json(result)
