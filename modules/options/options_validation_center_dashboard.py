"""
modules/options/options_validation_center_dashboard.py

Master Options Validation Command Center

Aggregates:

    ✓ Chain Validation
    ✓ Greeks Validation
    ✓ Pricing Validation
    ✓ Volatility Validation
    ✓ Liquidity Validation

Displays:

    Overall Score
    Overall Status
    PASS / WARN / FAIL Counts
    Engine Breakdown
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_validation_orchestrator import (
    run_full_options_validation,
)


# ============================================================
# HELPERS
# ============================================================

def _status_badge(status: str) -> str:

    status = str(status or "").upper()

    if status == "PASS":
        return "✅ PASS"

    if status == "WARN":
        return "⚠️ WARN"

    if status == "FAIL":
        return "❌ FAIL"

    return status


def _render_engine_summary(
    engine_statuses: dict[str, str]
):

    rows = []

    for engine_name, status in engine_statuses.items():

        if isinstance(status, dict):
            status = status.get("status", "UNKNOWN")

        status = str(status).upper()

        icon = {
            "PASS": "✅",
            "WARN": "⚠️",
            "FAIL": "❌",
        }.get(status, "•")

        rows.append({
            "Engine": engine_name.title(),
            "Status": f"{icon} {status}",
        })

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# DASHBOARD
# ============================================================

def render_options_validation_center_dashboard():

    st.subheader("📋 Options Validation Center")

    st.caption(
        "Runs Chain, Greeks, Pricing, Volatility, and Liquidity validation "
        "and produces an overall platform health score."
    )

    # =======================================================
    # INPUTS
    # =======================================================

    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:

        ticker = st.text_input(
            "Ticker",
            value="SPY",
            key="ovc_ticker",
        ).upper().strip()

    with col2:

        expiration = st.text_input(
            "Expiration (Optional)",
            value="",
            placeholder="YYYY-MM-DD",
            key="ovc_expiration",
        ).strip()

        if not expiration:
            expiration = None

    with col3:

        st.write("")

        run_validation = st.button(
            "Run Full Validation",
            key="ovc_run",
            use_container_width=True,
            type="primary",
        )

    # =======================================================
    # EXECUTE
    # =======================================================

    if run_validation:

        with st.spinner("Running full validation suite..."):

            result = run_full_options_validation(
                ticker=ticker,
                expiration=expiration,
            )

            st.session_state[
                "options_validation_center_result"
            ] = result

    result = st.session_state.get(
        "options_validation_center_result"
    )

    if not result:
        st.info(
            "Click 'Run Full Validation' to execute the complete validation suite."
        )
        return

    # =======================================================
    # METRICS
    # =======================================================

    overall_score = float(
        result.get("overall_score", 0)
    )

    overall_status = result.get(
        "overall_status",
        "UNKNOWN",
    )

    pass_count = result.get(
        "pass_count",
        0,
    )

    warn_count = result.get(
        "warn_count",
        0,
    )

    fail_count = result.get(
        "fail_count",
        0,
    )

    m1, m2, m3, m4, m5 = st.columns(5)

    m1.metric(
        "Overall Score",
        f"{overall_score:.2f}%"
    )

    m2.metric(
        "Status",
        overall_status,
    )

    m3.metric(
        "PASS",
        pass_count,
    )

    m4.metric(
        "WARN",
        warn_count,
    )

    m5.metric(
        "FAIL",
        fail_count,
    )

    st.divider()

    # =======================================================
    # ENGINE SUMMARY
    # =======================================================

    st.markdown("### Engine Summary")

    _render_engine_summary(
        result.get(
            "engine_counts",
            {},
        )
    )

    st.divider()

    # =======================================================
    # ENGINE STATUS
    # =======================================================

    st.markdown("### Validation Engines")

    engines = result.get(
        "engines",
        {},
    )

    for engine_name, payload in engines.items():

        with st.expander(
            f"{engine_name.title()} Validation",
            expanded=False,
        ):

            totals = payload.get(
                "totals",
                {},
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "PASS",
                totals.get(
                    "PASS",
                    0,
                )
            )

            c2.metric(
                "WARN",
                totals.get(
                    "WARN",
                    0,
                )
            )

            c3.metric(
                "FAIL",
                totals.get(
                    "FAIL",
                    0,
                )
            )

            st.json(payload)

    st.divider()

    # =======================================================
    # HEALTH ASSESSMENT
    # =======================================================

    st.markdown("### Platform Assessment")

    if overall_score >= 95:

        st.success(
            "Excellent options platform health. "
            "Validation suite shows very strong data quality."
        )

    elif overall_score >= 90:

        st.success(
            "Healthy options platform. "
            "Minor warnings may exist but validation passed."
        )

    elif overall_score >= 75:

        st.warning(
            "Validation completed with warnings. "
            "Review failing engines before relying on production decisions."
        )

    else:

        st.error(
            "Validation failed. "
            "Critical issues detected in one or more validation engines."
        )

    # =======================================================
    # RAW RESULT
    # =======================================================

    with st.expander(
        "Raw Validation Payload",
        expanded=False,
    ):
        st.json(result)