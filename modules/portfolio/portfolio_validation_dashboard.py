
"""
modules/portfolio/portfolio_validation_dashboard.py

Streamlit dashboard for portfolio validation.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import text

from modules.portfolio.portfolio_validation_engine import (
    portfolio_validation_frame,
    run_portfolio_validation,
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


def _get_portfolio_options(db: Any, tenant_id: str | None = None) -> dict[str, str]:
    try:
        where = ""
        params: dict[str, Any] = {}

        if tenant_id:
            where = "WHERE tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id

        rows = db.execute(
            text(
                f"""
                SELECT id, COALESCE(name, id::text) AS name
                FROM portfolios
                {where}
                ORDER BY created_at DESC NULLS LAST
                LIMIT 200
                """
            ),
            params,
        ).fetchall()

        return {f"{r[1]} | {r[0]}": str(r[0]) for r in rows}
    except Exception:
        return {}


def render_portfolio_validation_dashboard(
    db: Any,
    tenant_id: str | None = None,
):
    st.subheader("💼 Portfolio Validation Center")
    st.caption(
        "Read-only validation for positions, cash ledger, snapshots, closed trades, orders, and recommendations."
    )

    portfolio_options = _get_portfolio_options(db, tenant_id=tenant_id)

    c1, c2 = st.columns([3, 1])

    with c1:
        selected_portfolio_id = None

        if portfolio_options:
            selected_label = st.selectbox(
                "Portfolio",
                ["All Portfolios"] + list(portfolio_options.keys()),
                key="portfolio_validation_portfolio",
            )

            if selected_label != "All Portfolios":
                selected_portfolio_id = portfolio_options[selected_label]
        else:
            st.info("No portfolio list available. Validation will run across available scoped data.")

    with c2:
        run_clicked = st.button(
            "Run Validation",
            key="portfolio_validation_run",
            type="primary",
            use_container_width=True,
        )

    if run_clicked:
        with st.spinner("Running portfolio validation..."):
            st.session_state["portfolio_validation_result"] = run_portfolio_validation(
                db=db,
                tenant_id=tenant_id,
                portfolio_id=selected_portfolio_id,
            )

    result = st.session_state.get("portfolio_validation_result")

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

    df = portfolio_validation_frame(result)

    if df.empty:
        st.warning("No portfolio validation rows returned.")
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
        st.error("Portfolio validation failures detected.")
        st.dataframe(failures, use_container_width=True, hide_index=True)

    if not warnings.empty:
        st.warning("Portfolio validation warnings detected.")
        st.dataframe(warnings, use_container_width=True, hide_index=True)

    with st.expander("Raw Portfolio Validation Payload", expanded=False):
        st.json(result)
