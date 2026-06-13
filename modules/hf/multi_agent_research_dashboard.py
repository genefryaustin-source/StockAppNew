"""
modules/hf/multi_agent_research_dashboard.py

Streamlit dashboard for Stock HF-2 Multi-Agent Equity Research Analysts.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.hf.multi_agent_equity_orchestrator import run_multi_agent_research
from modules.hf.research_committee import build_committee_packet
from modules.hf.investment_council_legacy import build_investment_council_view



def render_multi_agent_research_dashboard(default_ticker: str = "SPY"):
    st.subheader("🧠 Multi-Agent Equity Research Analysts")
    st.caption("Specialized institutional analyst agents evaluate fundamentals, valuation, earnings, macro, sector, institutional flow, risk, and catalysts.")

    c1, c2 = st.columns([2, 1])
    with c1:
        ticker = st.text_input("Ticker", value=default_ticker, key="hf2_ticker").upper().strip()
    with c2:
        run_btn = st.button("Run Analyst Committee", type="primary", use_container_width=True, key=f"hf2_run_{ticker or 'NONE'}")

    context = _context_inputs()
    cache_key = f"hf2_report_{ticker}"
    if run_btn or cache_key not in st.session_state:
        if ticker:
            with st.spinner(f"Running multi-agent research committee for {ticker}..."):
                st.session_state[cache_key] = run_multi_agent_research(ticker, context)

    report = st.session_state.get(cache_key)
    if not report:
        st.info("Enter a ticker and run the analyst committee.")
        return

    consensus = report.get("consensus", {})
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Consensus", consensus.get("rating", "Hold"))
    m2.metric("Score", f"{consensus.get('score', 50):.1f}/100")
    m3.metric("Confidence", f"{consensus.get('confidence', 0):.1f}%")
    m4.metric("Agreement", f"{consensus.get('agreement', 0):.1f}%")
    m5.metric("Conviction", consensus.get("conviction", "Low"))

    tabs = st.tabs([
        "👥 Agent Views",
        "🗳 Committee Vote",
        "🎯 Investment Council",
        "⚖ Thesis Comparison",
        "📄 Research Memo",
    ])

    with tabs[0]:
        _render_agent_views(report)
    with tabs[1]:
        _render_committee_vote(report)
    with tabs[2]:
        _render_investment_council(report)
    with tabs[3]:
        _render_thesis_comparison(report)
    with tabs[4]:
        _render_research_memo(report)


def _context_inputs() -> dict:
    with st.expander("Optional Analyst Inputs", expanded=False):
        a, b, c, d = st.columns(4)
        context = {
            "revenue_growth": a.number_input("Revenue Growth %", value=8.0, key="hf2_rev_growth"),
            "eps_growth": b.number_input("EPS Growth %", value=7.0, key="hf2_eps_growth"),
            "gross_margin": c.number_input("Gross Margin %", value=45.0, key="hf2_gm"),
            "operating_margin": d.number_input("Operating Margin %", value=15.0, key="hf2_opm"),
            "fcf_margin": a.number_input("FCF Margin %", value=10.0, key="hf2_fcf"),
            "roic": b.number_input("ROIC %", value=12.0, key="hf2_roic"),
            "forward_pe": c.number_input("Forward P/E", value=22.0, key="hf2_pe"),
            "fcf_yield": d.number_input("FCF Yield %", value=4.0, key="hf2_fcfy"),
            "eps_revision_score": a.number_input("EPS Revision Score", value=0.0, key="hf2_eps_rev"),
            "sector_momentum": b.number_input("Sector Momentum", value=55.0, key="hf2_sector"),
            "smart_money_score": c.number_input("Smart Money Score", value=55.0, key="hf2_smart"),
            "beta": d.number_input("Beta", value=1.1, key="hf2_beta"),
        }
    return context


def _render_agent_views(report: dict):
    signals = report.get("signals", [])
    if not signals:
        st.info("No agent signals available.")
        return
    df = pd.DataFrame(signals)
    cols = [c for c in ["agent", "rating", "score", "confidence", "data_quality", "thesis"] if c in df.columns]
    st.dataframe(df[cols], use_container_width=True, hide_index=True)
    for sig in signals:
        with st.expander(f"{sig.get('agent')} — {sig.get('rating')} ({sig.get('score')})"):
            st.write(sig.get("thesis"))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Positives**")
                for p in sig.get("positives", []):
                    st.markdown(f"- {p}")
            with col2:
                st.markdown("**Risks**")
                for r in sig.get("risks", []):
                    st.markdown(f"- {r}")


def _render_committee_vote(report: dict):
    packet = build_committee_packet(report)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Decision", packet.get("decision", "Review"))
    c2.metric("Buy Votes", packet.get("buy_votes", 0))
    c3.metric("Hold Votes", packet.get("hold_votes", 0))
    c4.metric("Sell Votes", packet.get("sell_votes", 0))
    st.markdown("#### Bull Case")
    for item in packet.get("bull_case", []):
        st.markdown(f"- {item}")
    st.markdown("#### Bear Case")
    for item in packet.get("bear_case", []):
        st.markdown(f"- {item}")
    st.markdown("#### Required Actions")
    for item in packet.get("required_actions", []):
        st.markdown(f"- {item}")


def _render_investment_council(report: dict):
    council = build_investment_council_view(report)
    c1, c2, c3 = st.columns(3)
    c1.metric("Expected Return", f"{council.get('expected_return_pct', 0):+.1f}%")
    c2.metric("Risk / Reward", council.get("risk_reward", "—"))
    c3.metric("Council Action", council.get("council_action", "Monitor"))
    st.json({k: v for k, v in council.items() if k in {"bull_case", "base_case", "bear_case"}})


def _render_thesis_comparison(report: dict):
    signals = report.get("signals", [])
    rows = []
    for sig in signals:
        rows.append({
            "Agent": sig.get("agent"),
            "Rating": sig.get("rating"),
            "Score": sig.get("score"),
            "Confidence": sig.get("confidence"),
            "Top Positive": (sig.get("positives") or [""])[0],
            "Top Risk": (sig.get("risks") or [""])[0],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_research_memo(report: dict):
    packet = build_committee_packet(report)
    council = build_investment_council_view(report)
    memo = f"""# Multi-Agent Research Memo — {report.get('ticker')}

## Committee Recommendation
{packet.get('decision')}

## Consensus
Rating: {packet.get('consensus_rating')}  
Score: {packet.get('consensus_score')}  
Confidence: {packet.get('confidence')}%  
Agreement: {packet.get('agreement')}%

## Investment Council
Action: {council.get('council_action')}  
Expected Return: {council.get('expected_return_pct')}%  
Risk/Reward: {council.get('risk_reward')}

## Bull Case
"""
    for item in packet.get("bull_case", []):
        memo += f"- {item}\n"
    memo += "\n## Bear Case\n"
    for item in packet.get("bear_case", []):
        memo += f"- {item}\n"
    memo += "\n## Required Actions\n"
    for item in packet.get("required_actions", []):
        memo += f"- {item}\n"
    st.download_button("Download Memo", memo, file_name=f"{report.get('ticker')}_multi_agent_research_memo.md", mime="text/markdown")
    st.markdown(memo)
