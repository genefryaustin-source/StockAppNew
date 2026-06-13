from __future__ import annotations
from typing import Any
import pandas as pd
import streamlit as st

from .institutional_research_engine import build_institutional_research_report
from .research_ai_copilot import research_copilot_response


def _load_report(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    key = f"research_phase9_report_{ticker.upper()}"
    if force_refresh or key not in st.session_state:
        with st.spinner(f"Building institutional research report for {ticker.upper()}…"):
            st.session_state[key] = build_institutional_research_report(ticker)
    return st.session_state[key]


def _metric_row(scorecard: dict[str, Any]):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Composite Research", f"{scorecard.get('composite_research_score', 0):.1f}/100")
    c2.metric("Fundamental", f"{scorecard.get('fundamental_score', 0):.1f}")
    c3.metric("Institutional", f"{scorecard.get('institutional_score', 0):.1f}")
    c4.metric("Label", scorecard.get("research_label", "Neutral"))


def _show_records(records, height: int = 280):
    df = pd.DataFrame(records or [])
    if df.empty:
        st.info("No records available.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def render_research_command_center(ticker: str):
    st.subheader("🏛 Research Command Center")
    st.caption("Institutional research, market intelligence, thesis generation, and options-expression guidance.")
    c1, c2 = st.columns([1, 5])
    with c1:
        refresh = st.button("↺ Refresh Research", key=f"research_refresh_{ticker.upper()}", use_container_width=True)
    report = _load_report(ticker, force_refresh=refresh)
    components = report.get("components", {})
    scorecard = report.get("scorecard", {})
    thesis = report.get("thesis", {})
    validation = report.get("validation", {})
    _metric_row(scorecard)

    tabs = st.tabs([
        "📊 Fundamentals",
        "📈 Earnings",
        "🏦 Analysts",
        "🔄 Revisions",
        "🏛 Ownership",
        "🌎 Macro",
        "🏭 Sector",
        "📉 Regime",
        "⚡ Catalysts",
        "🎯 Thesis",
        "🤖 Copilot",
    ])

    with tabs[0]:
        f = components.get("fundamental", {})
        st.metric("Fundamental Score", f"{f.get('fundamental_score', 0):.1f}/100")
        _show_records(f.get("signals"))
    with tabs[1]:
        e = components.get("earnings", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Earnings Score", f"{e.get('earnings_score', 0):.1f}")
        c2.metric("Next Earnings", e.get("next_earnings_date", "—"))
        c3.metric("Setup", e.get("setup", "Balanced"))
        _show_records(e.get("history"))
    with tabs[2]:
        a = components.get("analyst", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Analyst Score", f"{a.get('analyst_score', 0):.1f}")
        c2.metric("Consensus", a.get("consensus", "Neutral"))
        c3.metric("Revision Momentum", f"{a.get('revision_momentum', 0):.1f}")
        for note in a.get("notes", []):
            st.caption(f"• {note}")
    with tabs[3]:
        r = components.get("revisions", {})
        st.metric("Revision Score", f"{r.get('revision_score', 0):.1f}/100", r.get("direction", "Neutral"))
        _show_records(r.get("table"))
    with tabs[4]:
        o = components.get("ownership", {})
        c1, c2 = st.columns(2)
        c1.metric("Institutional Score", f"{o.get('institutional_score', 0):.1f}")
        c2.metric("Ownership Read", o.get("ownership_read", "Neutral"))
        _show_records(o.get("activity"))
    with tabs[5]:
        m = components.get("macro", {})
        c1, c2 = st.columns(2)
        c1.metric("Macro Score", f"{m.get('macro_score', 0):.1f}")
        c2.metric("Macro Regime", m.get("regime", "Neutral"))
        _show_records(m.get("factors"))
    with tabs[6]:
        s = components.get("sector", {})
        c1, c2 = st.columns(2)
        c1.metric("Leading Sector", s.get("leading_sector", "—"))
        c2.metric("Lagging Sector", s.get("lagging_sector", "—"))
        _show_records(s.get("sectors"), height=340)
    with tabs[7]:
        rg = components.get("regime", {})
        c1, c2, c3 = st.columns(3)
        c1.metric("Regime", rg.get("regime", "Neutral"))
        c2.metric("Score", f"{rg.get('market_regime_score', 0):.1f}")
        c3.metric("Conditions", rg.get("conditions", "Transitional"))
        st.json(rg)
    with tabs[8]:
        c = components.get("catalysts", {})
        st.metric("Catalyst Score", f"{c.get('catalyst_score', 0):.1f}")
        _show_records(c.get("catalysts"), height=340)
    with tabs[9]:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Bull Thesis")
            for item in thesis.get("bull_thesis", []):
                st.success(item)
            st.markdown("#### Options Expression")
            st.info(thesis.get("options_expression", "Use defined-risk structures."))
        with c2:
            st.markdown("#### Bear / Risk Thesis")
            for item in thesis.get("bear_thesis", []):
                st.warning(item)
            st.markdown("#### Thesis Validation")
            st.metric("Confidence", f"{validation.get('confidence', 0):.1f}%")
            _show_records(validation.get("checks"))
    with tabs[10]:
        question = st.text_area("Ask the Research Copilot", value="What is the institutional thesis and best options expression?", key=f"research_q_{ticker.upper()}")
        if st.button("Run Research Copilot", key=f"research_copilot_{ticker.upper()}", type="primary"):
            st.markdown(research_copilot_response(ticker, report, question))
