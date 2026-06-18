"""
Sprint 4 Phase 4 — Volatility Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.options.options_data_service import get_options_chain
from modules.options.options_volatility_intelligence_engine import (
    build_volatility_intelligence_report,
    summarize_volatility_intelligence,
)


def _format_pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return str(value)


def _format_money(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return str(value)


def render_volatility_intelligence_dashboard(
    ticker: str,
    chain_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    st.subheader(f"🌪 Volatility Intelligence — {ticker.upper()}")
    st.caption("IV regime · Term structure · Skew · Expected move · Volatility strategy bias")

    if chain_data is None:
        with st.spinner(f"Loading options chain for {ticker.upper()}…"):
            chain_data = get_options_chain(ticker)

    if not chain_data or chain_data.get("error"):
        st.error((chain_data or {}).get("error", f"No chain data available for {ticker.upper()}"))
        return {}

    expirations = chain_data.get("expirations", [])
    if not expirations:
        st.warning("No expirations available for volatility intelligence.")
        return {}

    expiry = st.selectbox(
        "Expiration",
        expirations,
        index=0,
        key=f"vol_intel_expiry_{ticker.upper()}",
    )

    report = build_volatility_intelligence_report(chain_data, expiry)

    if not report.get("available"):
        st.warning(report.get("reason", "Volatility intelligence unavailable."))
        return report

    atm = report.get("atm", {})
    rank = report.get("rank", {})
    skew = report.get("skew", {})
    term = report.get("term", {})
    em = report.get("expected_move", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Vol Regime", report.get("volatility_regime", "—"))
    c2.metric("Strategy Bias", report.get("strategy_bias", "—"))
    c3.metric("ATM IV", _format_pct(atm.get("atm_iv_pct")))
    c4.metric("Expected Move", _format_money(em.get("expected_move")) if em.get("available") else "—")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("IV Rank Proxy", _format_pct(rank.get("iv_rank_proxy")) if rank.get("available") else "—")
    r2.metric("IV Percentile Proxy", _format_pct(rank.get("iv_percentile_proxy")) if rank.get("available") else "—")
    r3.metric("Skew Regime", skew.get("skew_regime", "—") if skew.get("available") else "—")
    r4.metric("Term Regime", term.get("term_regime", "—") if term.get("available") else "—")

    if em.get("available"):
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("Lower Range", _format_money(em.get("lower_range")))
        e2.metric("Upper Range", _format_money(em.get("upper_range")))
        e3.metric("Move %", _format_pct(em.get("expected_move_pct")))
        e4.metric("DTE", em.get("dte", "—"))

    st.markdown("#### Institutional Summary")
    st.markdown(f"- {summarize_volatility_intelligence(report)}")
    if rank.get("available"):
        st.markdown(f"- {rank.get('note')}")
    if skew.get("available"):
        st.markdown(
            f"- Skew: calls {skew.get('call_iv_pct')}%, puts {skew.get('put_iv_pct')}%, "
            f"put/call skew {skew.get('put_call_skew')}."
        )
    if term.get("available"):
        st.markdown(
            f"- Term structure: front IV {term.get('front_iv')}%, back IV {term.get('back_iv')}%, "
            f"slope {term.get('term_slope')}."
        )

    st.markdown("#### Volatility Opportunities")
    opps = report.get("opportunities", [])
    if opps:
        st.dataframe(pd.DataFrame(opps), use_container_width=True, hide_index=True)
    else:
        st.caption("No volatility opportunities detected.")

    with st.expander("Term Structure", expanded=False):
        term_table = term.get("term_structure")
        if isinstance(term_table, pd.DataFrame) and not term_table.empty:
            show = [c for c in ["expiry", "dte", "avg_iv_pct", "volume", "open_interest", "contracts"] if c in term_table.columns]
            st.dataframe(term_table[show], use_container_width=True, hide_index=True)
        else:
            st.caption("No term-structure table available.")

    return report
