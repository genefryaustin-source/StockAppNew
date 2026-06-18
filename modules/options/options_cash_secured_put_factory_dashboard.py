"""
Sprint 9 Phase 4 — Cash Secured Put Factory Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_cash_secured_put_factory_engine import (
    DEFAULT_CSP_POLICY,
    build_cash_secured_put_report,
    summarize_cash_secured_put_factory,
)


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_cash_secured_put_factory_dashboard(
    ticker: str = "",
    paper: bool = True,
    chain_data: dict | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏦 Cash Secured Put Factory")
    st.caption("Put candidate ranking · capital required · assignment probability · premium yield")

    with st.expander("Factory Policy", expanded=False):
        c1, c2, c3 = st.columns(3)
        portfolio_cash = c1.number_input("Portfolio Cash Available ($)", min_value=0.0, value=100000.0, step=1000.0, key="csp_factory_portfolio_cash")
        min_yield = c2.number_input("Minimum Annualized Yield %", min_value=0.0, max_value=100.0, value=float(DEFAULT_CSP_POLICY["min_annualized_yield"]), step=0.5, key="csp_factory_min_yield")
        max_assignment = c3.number_input("Max Assignment Probability %", min_value=0.0, max_value=100.0, value=float(DEFAULT_CSP_POLICY["max_assignment_probability"]), step=1.0, key="csp_factory_max_assignment")

        d1, d2, d3 = st.columns(3)
        delta_min = d1.number_input("Target Delta Min", min_value=0.0, max_value=1.0, value=float(DEFAULT_CSP_POLICY["target_delta_min"]), step=0.05, key="csp_factory_delta_min")
        delta_max = d2.number_input("Target Delta Max", min_value=0.0, max_value=1.0, value=float(DEFAULT_CSP_POLICY["target_delta_max"]), step=0.05, key="csp_factory_delta_max")
        cash_buffer = d3.number_input("Cash Buffer %", min_value=0.0, max_value=90.0, value=float(DEFAULT_CSP_POLICY["cash_buffer_pct"]), step=1.0, key="csp_factory_cash_buffer")

        e1, e2, e3 = st.columns(3)
        min_dte = e1.number_input("Min DTE", min_value=1, max_value=365, value=int(DEFAULT_CSP_POLICY["min_dte"]), step=1, key="csp_factory_min_dte")
        max_dte = e2.number_input("Max DTE", min_value=1, max_value=365, value=int(DEFAULT_CSP_POLICY["max_dte"]), step=1, key="csp_factory_max_dte")
        min_liquidity = e3.number_input("Min Liquidity Score", min_value=0, max_value=100, value=int(DEFAULT_CSP_POLICY["min_liquidity_score"]), step=5, key="csp_factory_min_liquidity")

    policy = dict(DEFAULT_CSP_POLICY)
    policy.update({
        "min_annualized_yield": float(min_yield),
        "max_assignment_probability": float(max_assignment),
        "target_delta_min": float(delta_min),
        "target_delta_max": float(delta_max),
        "cash_buffer_pct": float(cash_buffer),
        "min_dte": int(min_dte),
        "max_dte": int(max_dte),
        "min_liquidity_score": float(min_liquidity),
    })

    if chain_data is None:
        chain_key = f"opt_chain_{ticker}"
        payload = st.session_state.get(chain_key)
        chain_data = payload.get("data") if isinstance(payload, dict) and "data" in payload else payload

    if chain_data is None or (isinstance(chain_data, pd.DataFrame) and chain_data.empty):
        with st.spinner(f"Loading options chain for {ticker}…"):
            chain_data = get_options_chain(ticker)
            st.session_state[f"opt_chain_{ticker}"] = chain_data

    report = build_cash_secured_put_report(
        chain_data=chain_data,
        portfolio_cash=float(portfolio_cash),
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No CSP candidates available."))
        return report

    summary = report.get("summary", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Candidates", summary.get("candidate_count", 0))
    c2.metric("Approved", summary.get("approved_count", 0))
    c3.metric("Avg Yield", f"{summary.get('avg_annualized_yield', 0)}%")
    c4.metric("Top Score", f"{summary.get('top_opportunity_score', 0)}/100")

    d1, d2, d3 = st.columns(3)
    d1.metric("Available Cash", f"${summary.get('available_cash', 0):,.0f}")
    d2.metric("Top 10 Capital", f"${summary.get('top10_required_capital', 0):,.0f}")
    d3.metric("Avg Assignment", f"{summary.get('avg_assignment_probability', 0)}%")

    st.markdown("#### Cash Secured Put Factory Summary")
    st.info(summarize_cash_secured_put_factory(report))

    tab_approved, tab_all, tab_capital, tab_policy = st.tabs(["Approved Queue", "All Candidates", "Capital Allocation", "Policy"])

    show_cols = [
        "underlying", "option_symbol", "expiry", "dte", "strike", "bid", "ask", "mid",
        "volume", "open_interest", "iv", "delta", "Required Capital", "Premium Income",
        "Return On Capital %", "Annualized Yield %", "Assignment Probability %",
        "Opportunity Score", "Opportunity Quality", "Recommendation", "Factory Flags",
    ]

    with tab_approved:
        _table(report.get("approved"), show_cols + ["Contracts Fundable"])

    with tab_all:
        _table(report.get("candidates"), show_cols)

    with tab_capital:
        approved = report.get("approved")
        if isinstance(approved, pd.DataFrame) and not approved.empty:
            _table(approved, ["underlying", "option_symbol", "Required Capital", "Contracts Fundable", "Premium Income", "Annualized Yield %", "Assignment Probability %", "Opportunity Score"])
        else:
            st.caption("No approved capital allocation candidates.")

    with tab_policy:
        st.json(report.get("policy", {}))

    return report
