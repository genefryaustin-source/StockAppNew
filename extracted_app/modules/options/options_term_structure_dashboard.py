"""
Sprint 10 Phase 3 — Term Structure Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_term_structure_engine import (
    DEFAULT_TERM_STRUCTURE_POLICY,
    build_term_structure_report,
    summarize_term_structure,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_term_structure_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🧱 Term Structure Intelligence")
    st.caption("Expiry IV curve · contango/backwardation · curvature · calendar opportunities · vol carry")

    with st.expander("Term Structure Policy", expanded=False):
        c1, c2, c3 = st.columns(3)

        front_dte = c1.number_input(
            "Front DTE Max",
            min_value=1,
            max_value=120,
            value=int(DEFAULT_TERM_STRUCTURE_POLICY["front_dte_max"]),
            step=1,
            key="term_front_dte_max",
        )

        mid_dte = c2.number_input(
            "Mid DTE Max",
            min_value=1,
            max_value=365,
            value=int(DEFAULT_TERM_STRUCTURE_POLICY["mid_dte_max"]),
            step=1,
            key="term_mid_dte_max",
        )

        contango = c3.number_input(
            "Contango Threshold",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_TERM_STRUCTURE_POLICY["contango_threshold"]),
            step=0.01,
            key="term_contango_threshold",
        )

        d1, d2, d3 = st.columns(3)

        backwardation = d1.number_input(
            "Backwardation Threshold",
            min_value=-1.0,
            max_value=-0.01,
            value=float(DEFAULT_TERM_STRUCTURE_POLICY["backwardation_threshold"]),
            step=0.01,
            key="term_backwardation_threshold",
        )

        calendar_edge = d2.number_input(
            "Calendar Edge Threshold",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_TERM_STRUCTURE_POLICY["calendar_edge_threshold"]),
            step=0.01,
            key="term_calendar_edge_threshold",
        )

        steep_slope = d3.number_input(
            "Steep Slope Threshold",
            min_value=0.01,
            max_value=1.0,
            value=float(DEFAULT_TERM_STRUCTURE_POLICY["steep_slope_threshold"]),
            step=0.01,
            key="term_steep_slope_threshold",
        )

    policy = dict(DEFAULT_TERM_STRUCTURE_POLICY)
    policy.update({
        "front_dte_max": int(front_dte),
        "mid_dte_max": int(mid_dte),
        "contango_threshold": float(contango),
        "backwardation_threshold": float(backwardation),
        "calendar_edge_threshold": float(calendar_edge),
        "steep_slope_threshold": float(steep_slope),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_term_structure_report(
        chain_data=chain_data,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No term structure data available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Term Regime", summary.get("term_regime", "—"))
    c2.metric("Slope Quality", summary.get("slope_quality", "—"))
    c3.metric("Front IV", f"{summary.get('front_iv', 0):.4f}")
    c4.metric("Back IV", f"{summary.get('back_iv', 0):.4f}")

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Term Slope", f"{summary.get('term_slope', 0):.4f}")
    d2.metric("Curvature", f"{summary.get('curvature', 0):.4f}")
    d3.metric("Curve Shape", summary.get("curvature_regime", "—"))
    d4.metric("Opportunities", summary.get("opportunity_count", 0))

    st.markdown("#### Term Structure Summary")
    st.info(summarize_term_structure(report))

    tab_recs, tab_curve, tab_buckets, tab_opps, tab_state = st.tabs(
        [
            "Recommendations",
            "Expiry Curve",
            "Bucket Summary",
            "Calendar Opportunities",
            "Term State",
        ]
    )

    with tab_recs:
        _table(report.get("recommendations"))

    with tab_curve:
        _table(
            report.get("expiry_curve"),
            [
                "expiry",
                "dte",
                "term_bucket",
                "avg_iv",
                "median_iv",
                "min_iv",
                "max_iv",
                "contracts",
                "total_volume",
                "total_open_interest",
                "avg_vega",
                "iv_change",
                "slope_from_front",
                "annualized_carry_proxy",
            ],
        )

    with tab_buckets:
        _table(report.get("bucket_summary"))

    with tab_opps:
        _table((report.get("opportunities", {}) or {}).get("opportunities"))

    with tab_state:
        st.json(report.get("term_state", {}))
        st.json(report.get("policy", {}))

    return report
