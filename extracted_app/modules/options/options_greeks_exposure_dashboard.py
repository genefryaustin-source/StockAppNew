"""
Sprint 5 Phase 3 — Greeks Exposure Command Center Dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions
from modules.options.options_greeks_exposure_engine import (
    build_greeks_exposure_report,
    summarize_greeks_exposure,
)


def _fmt_num(value: Any) -> str:
    try:
        return f"{float(value):,.2f}"
    except Exception:
        return "—"


def _fmt_money(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def _table(df: Any, cols: list[str] | None = None) -> None:
    if isinstance(df, pd.DataFrame) and not df.empty:
        show = [c for c in (cols or list(df.columns)) if c in df.columns]
        st.dataframe(df[show], use_container_width=True, hide_index=True)
    else:
        st.caption("No table data available.")


def render_greeks_exposure_dashboard(
    ticker: str = "",
    paper: bool = True,
    positions: list[dict[str, Any]] | pd.DataFrame | None = None,
) -> dict[str, Any]:
    st.subheader("📈 Greeks Exposure Command Center")
    st.caption("Delta · Gamma · Theta · Vega · Charm · Vanna · Vomma exposure diagnostics")

    if positions is None:
        with st.spinner("Loading options portfolio positions…"):
            positions = load_portfolio_positions(ticker=ticker, paper=paper)

    report = build_greeks_exposure_report(positions)

    if not report.get("available"):
        st.info(report.get("reason", "No Greeks exposure data available."))
        return report

    score = report.get("score", {})
    net = report.get("net", {})
    greeks = net.get("net_greeks", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Greeks Risk", score.get("greeks_risk_level", "—"))
    c2.metric("Risk Score", f"{score.get('greeks_risk_score', 0)}/100")
    c3.metric("Positions", net.get("position_count", 0))
    c4.metric("Gross Notional", _fmt_money(net.get("gross_notional_proxy")))

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Net Delta", _fmt_num(greeks.get("delta", 0)))
    g2.metric("Net Gamma", _fmt_num(greeks.get("gamma", 0)))
    g3.metric("Net Theta", _fmt_num(greeks.get("theta", 0)))
    g4.metric("Net Vega", _fmt_num(greeks.get("vega", 0)))

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Net Charm", _fmt_num(greeks.get("charm", 0)))
    a2.metric("Net Vanna", _fmt_num(greeks.get("vanna", 0)))
    a3.metric("Net Vomma", _fmt_num(greeks.get("vomma", 0)))
    a4.metric("Net Rho", _fmt_num(greeks.get("rho", 0)))

    st.markdown("#### Exposure Summary")
    st.info(summarize_greeks_exposure(report))

    drivers = score.get("drivers", [])
    if drivers:
        st.markdown("#### Greeks Risk Drivers")
        for driver in drivers:
            st.markdown(f"- {driver}")

    tab_net, tab_underlying, tab_expiry, tab_strategy, tab_concentration, tab_curves, tab_positions = st.tabs(
        [
            "Net Greeks",
            "By Underlying",
            "By Expiration",
            "By Strategy",
            "Concentration",
            "Curves",
            "Positions",
        ]
    )

    with tab_net:
        rows = [{"Greek": k.title(), "Net Exposure": v, "Gross Exposure": net.get("gross_greeks", {}).get(k, 0)} for k, v in greeks.items()]
        _table(pd.DataFrame(rows))

        component_scores = score.get("component_scores", {})
        if component_scores:
            st.markdown("##### Risk Component Scores")
            _table(pd.DataFrame([
                {"Component": k.title(), "Score": v}
                for k, v in component_scores.items()
            ]))

    with tab_underlying:
        payload = report.get("by_underlying", {})
        _table(payload.get("by_underlying"))

    with tab_expiry:
        payload = report.get("by_expiry", {})
        _table(payload.get("by_expiry"))

    with tab_strategy:
        payload = report.get("by_strategy", {})
        _table(payload.get("by_strategy"))

    with tab_concentration:
        concentration = report.get("concentration", {})
        if concentration.get("available"):
            st.metric("Overall Concentration", concentration.get("concentration_level", "—"))
            _table(concentration.get("concentration"))
        else:
            st.caption(concentration.get("reason", "No concentration data available."))

    with tab_curves:
        curves = report.get("curves", {})
        curve = curves.get("curve")
        if isinstance(curve, pd.DataFrame) and not curve.empty:
            _table(curve)
            st.line_chart(
                curve.set_index("strike_bucket")[
                    [c for c in ["net_delta", "net_gamma", "net_theta", "net_vega"] if c in curve.columns]
                ]
            )
        else:
            st.caption("No exposure curve available.")

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
            "net_delta",
            "net_gamma",
            "net_theta",
            "net_vega",
            "net_charm",
            "net_vanna",
            "net_vomma",
        ]
        _table(positions_df, show_cols)

    return report
