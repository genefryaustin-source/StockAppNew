"""
Phase 10 — Multi-Agent Institutional Research Dashboard.
Designed to be called from modules/options/options_workstation_ui.py.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.research.agents.research_agent_registry import list_agents
from modules.research.agents.research_agent_orchestrator import run_research_agents
from modules.research.agents.research_committee import committee_vote
from modules.research.agents.thesis_adjudicator_agent import adjudicate_thesis
from modules.research.agents.investment_council import build_investment_council_view


def _fmt_score(v: Any) -> str:
    try:
        return f"{float(v):.1f}/100"
    except Exception:
        return "—"


def _run_or_get(ticker: str, force: bool = False) -> dict[str, Any]:
    key = f"multi_agent_research_{ticker.upper()}"
    if force or key not in st.session_state:
        with st.spinner(f"Running institutional research committee for {ticker.upper()}…"):
            report = run_research_agents(ticker)
            findings = report.get("findings", [])
            committee = committee_vote(findings)
            thesis = adjudicate_thesis(ticker, findings)
            council = build_investment_council_view(ticker, committee, thesis)
            report.update({"committee": committee, "thesis": thesis, "council": council})
            st.session_state[key] = report
    return st.session_state[key]


def render_multi_agent_research_dashboard(ticker: str):
    st.subheader("🧠 Multi-Agent Institutional Research Command")
    st.caption("Specialized analyst agents independently score the security, form a committee vote, and synthesize an investment council view.")

    c1, c2 = st.columns([1, 5])
    with c1:
        refresh = st.button("↺ Run Agents", key=f"multi_agent_refresh_{ticker.upper()}", use_container_width=True)

    report = _run_or_get(ticker, force=refresh)
    findings = report.get("findings", [])
    committee = report.get("committee", {})
    council = report.get("council", {})
    thesis = report.get("thesis", {})

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Committee Rating", committee.get("rating", "Hold"))
    m2.metric("Consensus Score", _fmt_score(committee.get("score", 50)))
    m3.metric("Confidence", _fmt_score(committee.get("confidence", 0)))
    m4.metric("Agreement", _fmt_score(committee.get("agreement_score", 0)))

    tabs = st.tabs([
        "👥 Agent Views",
        "🗳 Research Committee",
        "⚖ Consensus Engine",
        "🎯 Investment Council",
        "📊 Thesis Comparison",
        "🤖 AI Summary",
    ])

    with tabs[0]:
        _render_agent_views(findings)

    with tabs[1]:
        _render_committee(committee, findings)

    with tabs[2]:
        _render_consensus_engine(committee, findings)

    with tabs[3]:
        _render_investment_council(council)

    with tabs[4]:
        _render_thesis_comparison(thesis)

    with tabs[5]:
        _render_ai_summary(ticker, report)

    errors = report.get("errors") or []
    if errors:
        with st.expander("Agent runtime warnings", expanded=False):
            st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)


def _render_agent_views(findings: list[dict[str, Any]]):
    st.markdown("#### Specialist Analyst Views")
    if not findings:
        st.info("No agent findings available.")
        return
    rows = []
    for f in findings:
        rows.append({
            "Agent": f.get("agent"),
            "Rating": f.get("rating"),
            "Score": f.get("score"),
            "Confidence": f.get("confidence"),
            "Summary": f.get("summary"),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    for f in findings:
        with st.expander(f"{f.get('agent')} — {f.get('rating')} ({f.get('score')}/100)", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Positive Evidence**")
                for item in f.get("positives") or ["No positive evidence recorded."]:
                    st.markdown(f"- {item}")
            with col_b:
                st.markdown("**Risks / Pushback**")
                for item in f.get("risks") or ["No major risks recorded."]:
                    st.markdown(f"- {item}")
            if f.get("evidence"):
                st.json(f.get("evidence"))


def _render_committee(committee: dict[str, Any], findings: list[dict[str, Any]]):
    st.markdown("#### Research Committee Vote")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final Rating", committee.get("rating", "Hold"))
    c2.metric("Weighted Score", _fmt_score(committee.get("score", 50)))
    c3.metric("Agreement", _fmt_score(committee.get("agreement_score", 0)))
    c4.metric("Disagreement", _fmt_score(committee.get("disagreement_score", 0)))

    votes = committee.get("votes") or {}
    if votes:
        st.bar_chart(pd.DataFrame([{"Rating": k, "Votes": v} for k, v in votes.items()]).set_index("Rating"))

    st.markdown("**Committee Interpretation**")
    score = float(committee.get("score", 50) or 50)
    if score >= 68:
        st.success("The committee has a constructive view with enough cross-agent support to justify active consideration.")
    elif score >= 54:
        st.info("The committee is balanced. Further confirmation is needed before treating this as high conviction.")
    else:
        st.warning("The committee is cautious. Risk controls, hedges, or reduced sizing are preferred.")


def _render_consensus_engine(committee: dict[str, Any], findings: list[dict[str, Any]]):
    st.markdown("#### Consensus Engine")
    if not findings:
        st.info("No findings available.")
        return
    df = pd.DataFrame(findings)
    cols = [c for c in ["agent", "rating", "score", "confidence"] if c in df.columns]
    st.dataframe(df[cols].sort_values("score", ascending=False), use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Highest Conviction Agents**")
        top = df.sort_values(["confidence", "score"], ascending=False).head(5)
        st.dataframe(top[cols], use_container_width=True, hide_index=True)
    with c2:
        st.markdown("**Most Cautious Agents**")
        low = df.sort_values("score", ascending=True).head(5)
        st.dataframe(low[cols], use_container_width=True, hide_index=True)


def _render_investment_council(council: dict[str, Any]):
    st.markdown("#### Investment Council")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Recommendation", council.get("recommendation", "Hold"))
    c2.metric("Bull Prob", f"{council.get('bull_probability', 0):.1f}%")
    c3.metric("Base Prob", f"{council.get('base_probability', 0):.1f}%")
    c4.metric("Bear Prob", f"{council.get('bear_probability', 0):.1f}%")

    c5, c6 = st.columns(2)
    c5.metric("Expected Return Score", str(council.get("expected_return_score", "—")))
    c6.metric("Expected Risk Score", _fmt_score(council.get("expected_risk_score", 0)))

    probs = pd.DataFrame([
        {"Scenario": "Bull", "Probability": council.get("bull_probability", 0)},
        {"Scenario": "Base", "Probability": council.get("base_probability", 0)},
        {"Scenario": "Bear", "Probability": council.get("bear_probability", 0)},
    ])
    st.bar_chart(probs.set_index("Scenario"))


def _render_thesis_comparison(thesis: dict[str, Any]):
    st.markdown("#### Thesis Comparison")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Bull Case")
        for item in thesis.get("bull_case") or ["No bull case evidence available."]:
            st.markdown(f"- {item}")
    with col2:
        st.markdown("### Bear Case")
        for item in thesis.get("bear_case") or ["No bear case evidence available."]:
            st.markdown(f"- {item}")
    st.markdown("### Base Case")
    st.info(thesis.get("base_case", "No base case generated."))


def _render_ai_summary(ticker: str, report: dict[str, Any]):
    st.markdown("#### AI Research Committee Summary")
    if st.button("Generate Committee Summary", key=f"multi_agent_ai_summary_{ticker.upper()}", type="primary"):
        st.session_state[f"multi_agent_ai_summary_text_{ticker.upper()}"] = _build_summary_text(ticker, report)
    text = st.session_state.get(f"multi_agent_ai_summary_text_{ticker.upper()}") or _build_summary_text(ticker, report)
    st.markdown(text)


def _build_summary_text(ticker: str, report: dict[str, Any]) -> str:
    committee = report.get("committee", {})
    thesis = report.get("thesis", {})
    council = report.get("council", {})
    findings = report.get("findings", [])
    top = sorted(findings, key=lambda f: float(f.get("score", 50) or 50), reverse=True)[:3]
    low = sorted(findings, key=lambda f: float(f.get("score", 50) or 50))[:3]
    return f"""
### Institutional Research Committee Read — {ticker.upper()}

**Committee recommendation:** {committee.get('rating', 'Hold')} with a weighted score of {committee.get('score', 50)}/100 and confidence of {committee.get('confidence', 0)}/100.

**Investment council view:** Bull/Base/Bear probabilities are {council.get('bull_probability', 0)}% / {council.get('base_probability', 0)}% / {council.get('bear_probability', 0)}%.

**Most supportive analysts:** {', '.join(f.get('agent', '') for f in top)}.

**Most cautious analysts:** {', '.join(f.get('agent', '') for f in low)}.

**Base case:** {thesis.get('base_case', 'Balanced thesis pending more evidence.')}

**Actionability:** Use this committee read as upstream research input for the Strategy Command Center, Portfolio Command Center, and Execution Command Center. Do not treat it as an automatic trade instruction.
"""
