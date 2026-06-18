"""
Sprint 7 Phase 1 — Portfolio Hedging Intelligence Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_hedging_engine import (
    DEFAULT_HEDGE_POLICY,
    build_portfolio_hedging_report,
    summarize_portfolio_hedging,
)


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "—"


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_portfolio_hedging_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🛡 Portfolio Hedging Intelligence")
    st.caption("Hedge need · Delta hedge · Vega hedge · Tail-risk budget · Hedge candidate ranking")

    with st.expander("Hedge Policy", expanded=False):
        c1, c2, c3 = st.columns(3)
        portfolio_value = c1.number_input(
            "Portfolio Value ($)",
            min_value=1000.0,
            value=100000.0,
            step=1000.0,
            key="hedge_portfolio_value",
        )
        hedge_instrument_price = c2.number_input(
            "Hedge Instrument Price ($)",
            min_value=1.0,
            value=500.0,
            step=5.0,
            key="hedge_instrument_price",
            help="Example: SPY price or index hedge proxy.",
        )
        tail_budget_pct = c3.number_input(
            "Tail Hedge Budget %",
            min_value=0.0,
            max_value=20.0,
            value=float(DEFAULT_HEDGE_POLICY["tail_hedge_budget_pct"]) * 100,
            step=0.25,
            key="hedge_tail_budget_pct",
        ) / 100.0

        p1, p2, p3 = st.columns(3)
        max_delta_ratio = p1.number_input(
            "Max Delta Ratio",
            min_value=0.0,
            max_value=2.0,
            value=float(DEFAULT_HEDGE_POLICY["max_delta_ratio"]),
            step=0.05,
            key="hedge_max_delta_ratio",
        )
        max_vega_ratio = p2.number_input(
            "Max Vega Ratio",
            min_value=0.0,
            max_value=2.0,
            value=float(DEFAULT_HEDGE_POLICY["max_vega_ratio"]),
            step=0.05,
            key="hedge_max_vega_ratio",
        )
        crash_shock = p3.number_input(
            "Crash Shock %",
            min_value=-75.0,
            max_value=0.0,
            value=float(DEFAULT_HEDGE_POLICY["crash_shock"]) * 100,
            step=1.0,
            key="hedge_crash_shock",
        ) / 100.0

    policy = dict(DEFAULT_HEDGE_POLICY)
    policy.update({
        "tail_hedge_budget_pct": float(tail_budget_pct),
        "max_delta_ratio": float(max_delta_ratio),
        "max_vega_ratio": float(max_vega_ratio),
        "crash_shock": float(crash_shock),
    })

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_portfolio_hedging_report(
        positions=positions,
        portfolio_value=portfolio_value,
        hedge_instrument_price=hedge_instrument_price,
        policy=policy,
    )

    if not report.get("available"):
        st.info(report.get("reason", "No hedging data available."))
        return report

    need = report.get("hedge_need", {})
    effectiveness = report.get("effectiveness", {})
    delta = report.get("delta_hedge", {})
    vega = report.get("vega_hedge", {})
    tail = report.get("tail_budget", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Hedge Need", need.get("hedge_need_level", "—"))
    c2.metric("Need Score", f"{need.get('hedge_need_score', 0)}/100")
    c3.metric("Effectiveness", effectiveness.get("hedge_effectiveness_level", "—"))
    c4.metric("Tail Budget", _fmt_money(tail.get("tail_hedge_budget")))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Net Delta", _fmt_num(need.get("net_delta", 0)))
    g2.metric("Net Vega", _fmt_num(need.get("net_vega", 0)))
    g3.metric("Crash P&L", _fmt_money(need.get("crash_shock_pnl", 0)))
    g4.metric("Crash Loss %", f"{need.get('crash_loss_pct_notional', 0)}%")

    st.markdown("#### Hedging Summary")
    st.info(summarize_portfolio_hedging(report))

    drivers = need.get("drivers", [])
    if drivers:
        st.markdown("#### Hedge Need Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_candidates, tab_delta, tab_vega, tab_tail, tab_positions = st.tabs(
        [
            "Hedge Candidates",
            "Delta Hedge",
            "Vega Hedge",
            "Tail Budget",
            "Positions",
        ]
    )

    with tab_candidates:
        _table(report.get("hedge_candidates"))

    with tab_delta:
        st.json(delta)

    with tab_vega:
        st.json(vega)

    with tab_tail:
        st.json(tail)

    with tab_positions:
        positions_df = report.get("positions")
        show_cols = [
            "underlying",
            "option_symbol",
            "option_type",
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
