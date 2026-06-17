"""
modules/options/options_dealer_analytics_dashboard.py

Phase 2 Options Dealer Analytics Dashboard.
Renders dealer gamma/delta exposure, walls, zero-gamma, pin risk, and AI commentary.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
from modules.options.options_refresh_framework import render_refresh_controls

try:
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False

from modules.options.options_dealer_exposure_engine import build_dealer_exposure_report
from modules.options.options_dealer_ai import explain_dealer_exposure


def _fmt_money(v: Any) -> str:
    try:
        x = float(v or 0)
        sign = "-" if x < 0 else ""
        x = abs(x)
        if x >= 1_000_000_000:
            return f"{sign}${x/1_000_000_000:.2f}B"
        if x >= 1_000_000:
            return f"{sign}${x/1_000_000:.2f}M"
        if x >= 1_000:
            return f"{sign}${x/1_000:.1f}K"
        return f"{sign}${x:,.0f}"
    except Exception:
        return "—"


def _load_dealer_report(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    cache_key = f"dealer_exposure_report_{ticker.upper()}"
    if force_refresh or cache_key not in st.session_state:
        st.session_state[cache_key] = build_dealer_exposure_report(ticker)
    return st.session_state[cache_key]


def render_options_dealer_analytics_dashboard(ticker: str):
    """Render Phase 2 dealer analytics."""
    clean_ticker = ticker.upper().strip()
    st.subheader(f"🧲 Dealer Analytics Center — {clean_ticker}")
    st.caption("Gamma exposure · delta exposure · zero-gamma · walls · pin risk · hedging pressure")

    refresh_state = render_refresh_controls(
        "options_dealer",
        ticker if "ticker" in locals() else clean_ticker if "clean_ticker" in locals() else "",
        cache_prefixes=['dealer_exposure_report_', 'dealer_ai_'],
        default_mode="1 Minute",
    )


    c_refresh, c_note = st.columns([1, 5])
    with c_refresh:
        refresh = st.button(
            "↺ Refresh",
            key=f"dealer_refresh_{clean_ticker}",
            use_container_width=True,
        )
    with c_note:
        st.caption("Uses existing options chain data. Live opening/closing side is not required for this estimated dealer positioning layer.")

    report = _load_dealer_report(clean_ticker, force_refresh=refresh)
    if report.get("error"):
        st.warning(report.get("error"))
        return

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Spot", f"${float(report.get('spot') or 0):,.2f}")
    c2.metric("Net GEX", _fmt_money(report.get("total_gex")))
    c3.metric("Net DEX", _fmt_money(report.get("total_dex")))
    c4.metric("Gamma State", report.get("net_gamma_state", "—"))
    c5.metric("Pin Risk", f"${report.get('pin_risk_strike'):,.2f}" if report.get("pin_risk_strike") else "—", f"{report.get('pin_risk_score', 0):.0f}/100")

    st.info(report.get("hedging_pressure", "Dealer hedging pressure unavailable."))

    tabs = st.tabs([
        "Gamma Exposure",
        "Delta Exposure",
        "Walls & Zero Gamma",
        "Pin Risk",
        "Expiration Exposure",
        "Top Contracts",
        "AI Dealer Read",
    ])

    with tabs[0]:
        _render_gamma_exposure(report)
    with tabs[1]:
        _render_delta_exposure(report)
    with tabs[2]:
        _render_walls(report)
    with tabs[3]:
        _render_pin_risk(report)
    with tabs[4]:
        _render_expiration_exposure(report)
    with tabs[5]:
        _render_top_contracts(report)
    with tabs[6]:
        _render_ai_dealer_read(clean_ticker, report)


def _render_gamma_exposure(report: dict[str, Any]):
    st.markdown("#### Gamma Exposure by Strike")
    rows = report.get("gamma_by_strike") or []
    if not rows:
        st.info("No gamma exposure rows available.")
        return
    df = pd.DataFrame(rows)
    if PLOTLY and not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["strike"], y=df["total_exposure"], name="Net GEX"))
        spot = report.get("spot")
        if spot:
            fig.add_vline(x=float(spot), line_dash="dash", annotation_text="Spot")
        zg = report.get("zero_gamma")
        if zg:
            fig.add_vline(x=float(zg), line_dash="dot", annotation_text="Zero Γ")
        fig.update_layout(height=420, xaxis_title="Strike", yaxis_title="Estimated Gamma Exposure", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_delta_exposure(report: dict[str, Any]):
    st.markdown("#### Delta Exposure by Strike")
    rows = report.get("delta_by_strike") or []
    if not rows:
        st.info("No delta exposure rows available.")
        return
    df = pd.DataFrame(rows)
    if PLOTLY and not df.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["strike"], y=df["total_exposure"], name="Net DEX"))
        spot = report.get("spot")
        if spot:
            fig.add_vline(x=float(spot), line_dash="dash", annotation_text="Spot")
        fig.update_layout(height=420, xaxis_title="Strike", yaxis_title="Estimated Delta Exposure", template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_walls(report: dict[str, Any]):
    st.markdown("#### Walls, Magnets, and Zero-Gamma")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zero Gamma", f"${report.get('zero_gamma'):,.2f}" if report.get("zero_gamma") else "—")
    c2.metric("Call Wall", f"${report.get('gamma_wall_call'):,.2f}" if report.get("gamma_wall_call") else "—")
    c3.metric("Put Wall", f"${report.get('gamma_wall_put'):,.2f}" if report.get("gamma_wall_put") else "—")
    c4.metric("Strongest Wall", f"${report.get('strongest_wall'):,.2f}" if report.get("strongest_wall") else "—")
    notes = report.get("notes") or []
    for note in notes:
        st.caption(f"• {note}")


def _render_pin_risk(report: dict[str, Any]):
    st.markdown("#### Pin Risk")
    c1, c2 = st.columns(2)
    c1.metric("Pin Strike", f"${report.get('pin_risk_strike'):,.2f}" if report.get("pin_risk_strike") else "—")
    c2.metric("Pin Score", f"{float(report.get('pin_risk_score') or 0):.1f}/100")
    if float(report.get("pin_risk_score") or 0) >= 70:
        st.warning("Elevated pin risk. Price may gravitate toward the high-open-interest strike near expiration, but this is not guaranteed.")
    elif float(report.get("pin_risk_score") or 0) >= 40:
        st.info("Moderate pin risk. Monitor open interest concentration and price distance into expiration.")
    else:
        st.success("Low pin-risk signal from current chain data.")


def _render_expiration_exposure(report: dict[str, Any]):
    st.markdown("#### Exposure by Expiration")
    rows = report.get("expiration_exposure") or []
    if not rows:
        st.info("No expiration exposure rows available.")
        return
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_top_contracts(report: dict[str, Any]):
    st.markdown("#### Top Exposure Contracts")
    gamma_df = pd.DataFrame(report.get("top_gamma_contracts") or [])
    delta_df = pd.DataFrame(report.get("top_delta_contracts") or [])
    tab_g, tab_d = st.tabs(["Top Gamma", "Top Delta"])
    with tab_g:
        if gamma_df.empty:
            st.info("No top gamma contracts.")
        else:
            st.dataframe(gamma_df, use_container_width=True, hide_index=True)
    with tab_d:
        if delta_df.empty:
            st.info("No top delta contracts.")
        else:
            st.dataframe(delta_df, use_container_width=True, hide_index=True)


def _render_ai_dealer_read(ticker: str, report: dict[str, Any]):
    st.markdown("#### AI Dealer Positioning Read")
    key = f"dealer_ai_commentary_{ticker}"
    if st.button("Generate AI Dealer Commentary", key=f"dealer_ai_btn_{ticker}", type="primary"):
        with st.spinner("Generating dealer-positioning commentary…"):
            st.session_state[key] = explain_dealer_exposure(report)
    if st.session_state.get(key):
        st.markdown(st.session_state[key])
    else:
        st.caption("Generate commentary to summarize gamma state, hedging pressure, walls, and pin-risk levels.")
