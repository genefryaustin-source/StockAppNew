"""
modules/options/options_ai_institutional_dashboard.py

Phase 3 — Institutional Options Copilot dashboard.
Adds AI-style reasoning tabs on top of Smart Money and Dealer Analytics.
"""
from __future__ import annotations

from typing import Any
import json

import pandas as pd
import streamlit as st

from modules.options.options_institutional_copilot import build_institutional_copilot_report


def _money(v: Any) -> str:
    try:
        return f"${float(v):,.0f}"
    except Exception:
        return "—"


def _pct(v: Any) -> str:
    try:
        return f"{float(v):.1%}"
    except Exception:
        return "—"


def _load_report(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    key = f"institutional_copilot_report_{ticker.upper()}"
    if force_refresh or key not in st.session_state:
        with st.spinner(f"Building institutional options copilot report for {ticker.upper()}…"):
            st.session_state[key] = build_institutional_copilot_report(ticker)
    return st.session_state[key]


def render_options_institutional_copilot_dashboard(ticker: str):
    st.subheader(f"🧠 Institutional Options Copilot — {ticker.upper()}")
    st.caption("Institutional thesis · positioning analysis · dealer intelligence · conviction ranking · trade ideas")

    c_refresh, c_note = st.columns([1, 5])
    with c_refresh:
        refresh = st.button("↺ Refresh", key=f"institutional_copilot_refresh_{ticker.upper()}", use_container_width=True)
    with c_note:
        st.caption("Uses Phase 1 Smart Money + Phase 2 Dealer Analytics. This is decision support, not trade execution advice.")

    report = _load_report(ticker, force_refresh=refresh)
    if report.get("error"):
        st.warning(report.get("error"))
        with st.expander("Raw diagnostic payload", expanded=False):
            st.json(report)
        return

    thesis = report.get("institutional_thesis", {})
    positioning = report.get("positioning", {})
    mm = report.get("market_maker_intelligence", {})
    conviction = report.get("conviction", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Institutional Direction", thesis.get("direction", "Neutral"))
    m2.metric("Direction Score", f"{thesis.get('direction_score', 50)}/100")
    m3.metric("Conviction", f"{conviction.get('score', 0)}/100", conviction.get("label", "Low"))
    m4.metric("Strike Magnet", str((positioning.get("strike_magnet") or {}).get("value") or "—"))

    tabs = st.tabs([
        "🧠 Thesis",
        "🎯 Positioning",
        "🏦 Dealer Intelligence",
        "🔥 Conviction",
        "📈 Trade Ideas",
        "⚠ Risk Factors",
        "🧾 Raw Report",
    ])

    with tabs[0]:
        st.markdown("#### Institutional Thesis")
        st.success(thesis.get("summary", "No thesis available."))
        obs = thesis.get("observations", [])
        if obs:
            st.markdown("**Key observations**")
            for item in obs:
                st.markdown(f"- {item}")

    with tabs[1]:
        st.markdown("#### Positioning Analysis")
        p1, p2, p3, p4 = st.columns(4)
        strike = positioning.get("strike_magnet") or {}
        expiry = positioning.get("expiry_magnet") or {}
        p1.metric("Strike Magnet", str(strike.get("value") or "—"))
        p2.metric("Strike Premium", _money(strike.get("premium")))
        p3.metric("Expiry Magnet", str(expiry.get("value") or "—"))
        p4.metric("Premium Concentration", _pct(positioning.get("premium_concentration")))
        st.info(positioning.get("summary", "No positioning summary available."))
        st.json({k: positioning.get(k) for k in ["consensus", "magnet_strength", "contract_count", "call_premium", "put_premium"]})

    with tabs[2]:
        st.markdown("#### Dealer / Market Maker Intelligence")
        d1, d2, d3 = st.columns(3)
        d1.metric("Hedging Regime", mm.get("hedging_regime", "Neutral"))
        d2.metric("Zero Gamma", str(mm.get("zero_gamma") or "—"))
        d3.metric("Gamma Wall", str(mm.get("gamma_wall") or "—"))
        st.warning(mm.get("hedging_pressure", "Dealer hedging pressure unavailable."))
        watch = mm.get("watch_levels") or []
        if watch:
            st.markdown("**Watch levels**")
            st.dataframe(pd.DataFrame({"Level": watch}), use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown("#### Conviction Ranking")
        st.metric("Copilot Conviction", f"{conviction.get('score', 0)}/100", conviction.get("label", "Low"))
        reasons = conviction.get("reasons", [])
        for r in reasons:
            st.markdown(f"- {r}")

    with tabs[4]:
        st.markdown("#### Trade Ideas")
        recs = report.get("trade_recommendations") or []
        if recs:
            st.dataframe(pd.DataFrame(recs), use_container_width=True, hide_index=True)
        else:
            st.info("No trade ideas generated.")

    with tabs[5]:
        st.markdown("#### Risk Factors")
        for risk in report.get("risk_factors", []):
            st.markdown(f"- ⚠️ {risk}")

    with tabs[6]:
        with st.expander("Full JSON Report", expanded=False):
            st.code(json.dumps(report, indent=2, default=str))
