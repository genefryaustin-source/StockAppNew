"""
Sprint 5 Phase 2 — Portfolio Stress Testing Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_stress_testing_engine import (
    build_portfolio_stress_report,
    summarize_portfolio_stress,
)


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def render_stress_testing_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("🔥 Portfolio Stress Testing")
    st.caption("Crash scenarios · Vol shocks · Liquidity stress · VaR · Survival score")

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_portfolio_stress_report(positions)

    if not report.get("available"):
        st.info(report.get("reason", "No stress test data available."))
        return report

    survival = report.get("survival", {})
    scenarios = report.get("scenarios", {})
    worst = scenarios.get("worst_case", {})
    best = scenarios.get("best_case", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Survival Level", survival.get("survival_level", "—"))
    c2.metric("Survival Score", f"{survival.get('survival_score', 0)}/100")
    c3.metric("Worst Scenario", worst.get("Scenario", "—"))
    c4.metric("Worst P&L", _fmt_money(worst.get("Total P&L")))

    st.markdown("#### Stress Summary")
    st.info(summarize_portfolio_stress(report))

    drivers = survival.get("drivers", [])
    if drivers:
        st.markdown("#### Stress Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_scenarios, tab_liquidity, tab_var, tab_positions = st.tabs(
        [
            "Named Scenarios",
            "Liquidity Stress",
            "VaR",
            "Positions",
        ]
    )

    with tab_scenarios:
        s1, s2, s3 = st.columns(3)
        s1.metric("Gross Notional", _fmt_money(scenarios.get("gross_notional_proxy")))
        s2.metric("Best P&L", _fmt_money(best.get("Total P&L")))
        s3.metric("Worst P&L", _fmt_money(worst.get("Total P&L")))

        table = scenarios.get("scenarios")
        if isinstance(table, pd.DataFrame) and not table.empty:
            st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption("No named scenario table available.")

    with tab_liquidity:
        liquidity = report.get("liquidity", {})
        if liquidity.get("available"):
            l1, l2 = st.columns(2)
            l1.metric("Base Exit Cost", _fmt_money(liquidity.get("base_exit_cost")))
            worst_exit = liquidity.get("worst_exit_cost", {})
            l2.metric("Worst Exit Cost", _fmt_money(worst_exit.get("Estimated Exit Cost")))

            table = liquidity.get("liquidity")
            if isinstance(table, pd.DataFrame) and not table.empty:
                st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption(liquidity.get("reason", "No liquidity stress data."))

    with tab_var:
        var_result = report.get("var", {})
        if var_result.get("available"):
            v1, v2 = st.columns(2)
            v1.metric("Exposure Proxy", _fmt_money(var_result.get("exposure_proxy")))
            v2.metric("Gross Notional", _fmt_money(var_result.get("gross_notional_proxy")))

            table = var_result.get("var")
            if isinstance(table, pd.DataFrame) and not table.empty:
                st.dataframe(table, use_container_width=True, hide_index=True)
        else:
            st.caption(var_result.get("reason", "No VaR data."))

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
                "notional_proxy",
                "net_delta",
                "net_gamma",
                "net_theta",
                "net_vega",
            ]
            show_cols = [c for c in show_cols if c in positions_df.columns]
            st.dataframe(positions_df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.caption("No positions available.")

    return report
