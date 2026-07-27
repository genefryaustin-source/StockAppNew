"""
Sprint 5 Phase 5 — Portfolio Construction Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_construction_engine import (
    DEFAULT_TARGETS,
    build_portfolio_construction_report,
    summarize_portfolio_construction,
)


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def _fmt_pct(value: Any) -> str:
    try:
        return f"{float(value):.2f}%"
    except Exception:
        return "—"


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_portfolio_construction_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🏗 Portfolio Construction Intelligence")
    st.caption("Capital allocation · Strategy mix · Risk budget · Diversification · Rebalancing recommendations")

    with st.expander("Construction Targets", expanded=False):
        c1, c2, c3 = st.columns(3)
        max_underlying = c1.number_input(
            "Max Underlying Allocation %",
            min_value=5.0,
            max_value=100.0,
            value=float(DEFAULT_TARGETS["max_underlying_share"]),
            step=5.0,
            key="construction_max_underlying",
        )
        max_expiry = c2.number_input(
            "Max Expiry Allocation %",
            min_value=5.0,
            max_value=100.0,
            value=float(DEFAULT_TARGETS["max_expiry_share"]),
            step=5.0,
            key="construction_max_expiry",
        )
        max_strategy = c3.number_input(
            "Max Strategy Allocation %",
            min_value=5.0,
            max_value=100.0,
            value=float(DEFAULT_TARGETS["max_strategy_share"]),
            step=5.0,
            key="construction_max_strategy",
        )

        t1, t2 = st.columns(2)
        min_strategy_count = t1.number_input(
            "Minimum Strategy Count",
            min_value=1,
            max_value=20,
            value=int(DEFAULT_TARGETS["min_strategy_count"]),
            step=1,
            key="construction_min_strategy_count",
        )
        target_hedge = t2.number_input(
            "Target Hedge Share %",
            min_value=0.0,
            max_value=100.0,
            value=float(DEFAULT_TARGETS["target_hedge_share"]),
            step=5.0,
            key="construction_target_hedge",
        )

    targets = dict(DEFAULT_TARGETS)
    targets.update({
        "max_underlying_share": float(max_underlying),
        "max_expiry_share": float(max_expiry),
        "max_strategy_share": float(max_strategy),
        "min_strategy_count": int(min_strategy_count),
        "target_hedge_share": float(target_hedge),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_portfolio_construction_report(positions, targets=targets)

    if not report.get("available"):
        st.info(report.get("reason", "No portfolio construction data available."))
        return report

    score = report.get("score", {})
    diversification = report.get("diversification", {})
    allocation = report.get("allocation", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Construction Level", score.get("construction_level", "—"))
    c2.metric("Construction Score", f"{score.get('construction_score', 0)}/100")
    c3.metric("Diversification", diversification.get("diversification_level", "—"))
    c4.metric("Gross Notional", _fmt_money(allocation.get("gross_notional_proxy")))

    d1, d2, d3 = st.columns(3)
    d1.metric("Top Underlying", _fmt_pct(diversification.get("max_underlying_allocation")))
    d2.metric("Top Expiry", _fmt_pct(diversification.get("max_expiry_allocation")))
    d3.metric("Top Strategy", _fmt_pct(diversification.get("max_strategy_allocation")))

    st.markdown("#### Construction Summary")
    st.info(summarize_portfolio_construction(report))

    drivers = score.get("drivers", [])
    if drivers:
        st.markdown("#### Construction Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_alloc, tab_strategy, tab_risk, tab_div, tab_recs, tab_positions = st.tabs(
        [
            "Allocation",
            "Strategy Mix",
            "Risk Budget",
            "Diversification",
            "Recommendations",
            "Positions",
        ]
    )

    with tab_alloc:
        st.markdown("##### By Underlying")
        _table(allocation.get("by_underlying"))

        st.markdown("##### By Expiry")
        _table(allocation.get("by_expiry"))

        st.markdown("##### By Strategy")
        _table(allocation.get("by_strategy"))

    with tab_strategy:
        strategy_mix = report.get("strategy_mix", {})
        st.markdown("##### Strategy Buckets")
        _table(strategy_mix.get("by_bucket"))

        st.markdown("##### Strategy Detail")
        _table(strategy_mix.get("by_strategy"))

    with tab_risk:
        rb = report.get("risk_budget", {})
        st.metric("Total Risk Budget", rb.get("total_risk_budget", "—"))

        st.markdown("##### Risk Budget by Bucket")
        _table(rb.get("risk_by_bucket"))

        st.markdown("##### Risk Budget by Underlying")
        _table(rb.get("risk_by_underlying"))

    with tab_div:
        st.metric("Diversification Level", diversification.get("diversification_level", "—"))
        st.metric("Diversification Score", f"{diversification.get('diversification_score', 0)}/100")

        st.markdown("##### Diversification Issues")
        for issue in diversification.get("issues", []):
            st.markdown(f"- {issue}")

    with tab_recs:
        recs = report.get("recommendations", {}).get("recommendations")
        _table(recs)

    with tab_positions:
        positions_df = report.get("positions")
        show_cols = [
            "underlying",
            "option_symbol",
            "option_type",
            "strategy",
            "expiry",
            "strike",
            "qty",
            "market_value",
            "notional_proxy",
            "net_delta",
            "net_gamma",
            "net_theta",
            "net_vega",
        ]
        _table(positions_df, show_cols)

    return report
