"""
Sprint 5 Phase 1 — Options Portfolio Risk Dashboard.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_portfolio_risk_engine import (
    build_portfolio_risk_report,
    summarize_portfolio_risk,
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


def _render_greeks_table(greeks: dict[str, Any]) -> None:
    if not greeks:
        st.caption("No Greek exposure available.")
        return

    rows = [{"Greek": k.title(), "Net Exposure": v} for k, v in greeks.items()]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_portfolio_risk_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🛡 Portfolio Risk Engine")
    st.caption("Net Greeks · Concentration risk · Shock scenarios · Largest risk contributors")

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_portfolio_risk_report(positions)

    if not report.get("available"):
        st.info(report.get("reason", "No portfolio risk data available."))
        return report

    score = report.get("risk_score", {})
    net = report.get("net_greeks", {})
    greeks = net.get("greeks", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk Level", score.get("risk_level", "—"))
    c2.metric("Risk Score", f"{score.get('risk_score', 0)}/100")
    c3.metric("Positions", net.get("position_count", 0))
    c4.metric("Gross Notional", _fmt_money(net.get("gross_notional_proxy")))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Net Delta", _fmt_num(greeks.get("delta", 0)))
    g2.metric("Net Gamma", _fmt_num(greeks.get("gamma", 0)))
    g3.metric("Net Theta", _fmt_num(greeks.get("theta", 0)))
    g4.metric("Net Vega", _fmt_num(greeks.get("vega", 0)))

    st.markdown("#### Risk Summary")
    st.info(summarize_portfolio_risk(report))

    drivers = score.get("drivers", [])
    if drivers:
        st.markdown("#### Key Risk Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_greeks, tab_conc, tab_scenarios, tab_contrib, tab_positions = st.tabs(
        [
            "Greeks",
            "Concentration",
            "Shock Scenarios",
            "Risk Contributors",
            "Positions",
        ]
    )

    with tab_greeks:
        _render_greeks_table(greeks)

    with tab_conc:
        concentration = report.get("concentration", {})
        if concentration.get("available"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Concentration Risk", concentration.get("risk_level", "—"))
            c2.metric("Top Underlying Share", f"{concentration.get('top_underlying_share', 0)}%")
            c3.metric("Top Expiry Share", f"{concentration.get('top_expiry_share', 0)}%")

            st.markdown("##### By Underlying")
            by_underlying = concentration.get("by_underlying")
            if isinstance(by_underlying, pd.DataFrame) and not by_underlying.empty:
                st.dataframe(by_underlying, use_container_width=True, hide_index=True)

            st.markdown("##### By Expiry")
            by_expiry = concentration.get("by_expiry")
            if isinstance(by_expiry, pd.DataFrame) and not by_expiry.empty:
                st.dataframe(by_expiry, use_container_width=True, hide_index=True)
        else:
            st.caption(concentration.get("reason", "No concentration data."))

    with tab_scenarios:
        scenarios = report.get("scenarios", {})
        if scenarios.get("available"):
            worst = scenarios.get("worst_case", {})
            best = scenarios.get("best_case", {})

            s1, s2 = st.columns(2)
            s1.metric("Worst Shock P&L", _fmt_money(worst.get("Estimated P&L")))
            s2.metric("Best Shock P&L", _fmt_money(best.get("Estimated P&L")))

            table = scenarios.get("scenarios")
            if isinstance(table, pd.DataFrame) and not table.empty:
                st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption(scenarios.get("reason", "No scenario data."))

    with tab_contrib:
        contributors = report.get("contributors", {})
        table = contributors.get("contributors")
        if isinstance(table, pd.DataFrame) and not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption(contributors.get("reason", "No contributors available."))

    with tab_positions:
        positions_df = report.get("positions")
        if isinstance(positions_df, pd.DataFrame) and not positions_df.empty:
            show_cols = [
                "underlying",
                "option_symbol",
                "option_type",
                "expiry",
                "strike",
                "qty",
                "market_value",
                "unrealized_pnl",
                "net_delta",
                "net_gamma",
                "net_theta",
                "net_vega",
            ]
            show_cols = [c for c in show_cols if c in positions_df.columns]
            st.dataframe(positions_df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.caption("No position table available.")

    return report
