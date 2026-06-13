"""Streamlit dashboard for Phase 11 Autonomous Portfolio Manager."""
from __future__ import annotations
import pandas as pd
import streamlit as st

from modules.portfolio.autonomous_pm.portfolio_state_engine import build_portfolio_state
from modules.portfolio.autonomous_pm.portfolio_allocation_engine import calculate_allocation_plan
from modules.portfolio.autonomous_pm.portfolio_rebalance_engine import build_rebalance_plan
from modules.portfolio.autonomous_pm.portfolio_hedging_engine import generate_hedge_candidates
from modules.portfolio.autonomous_pm.portfolio_trade_generation_engine import generate_trade_candidates
from modules.portfolio.autonomous_pm.portfolio_governance_engine import evaluate_governance
from modules.portfolio.autonomous_pm.portfolio_memory_engine import record_pm_decision, get_pm_decisions
from modules.portfolio.autonomous_pm.portfolio_ai import explain_autonomous_pm_report


def _report(ticker: str, paper: bool, risk_budget: float, autopilot_level: int) -> dict:
    state = build_portfolio_state(ticker, paper=paper, risk_budget=risk_budget)
    allocation = calculate_allocation_plan(state)
    rebalance = build_rebalance_plan(state, allocation)
    hedges = generate_hedge_candidates(ticker, state)
    trades = generate_trade_candidates(ticker, state, rebalance, allocation)
    governance = evaluate_governance(trades, autopilot_level=autopilot_level)
    return {"state": state, "allocation": allocation, "rebalance": rebalance, "hedges": hedges, "trades": trades, "governance": governance}


def render_autonomous_portfolio_manager_dashboard(ticker: str, paper: bool = True):
    st.subheader("🤖 Autonomous Portfolio Manager")
    st.caption("Phase 11 · Portfolio brain · allocation · rebalance · hedging · governance · autonomous PM copilot")

    c1, c2, c3 = st.columns(3)
    risk_budget = c1.number_input("Risk Budget", min_value=1000.0, max_value=10000000.0, value=100000.0, step=5000.0, key=f"apm_risk_budget_{ticker}")
    autopilot_level = c2.slider("Autopilot Level", 0, 5, 1, key=f"apm_autopilot_{ticker}")
    refresh = c3.button("↺ Refresh PM", key=f"apm_refresh_{ticker}", use_container_width=True)

    key = f"apm_report_{ticker}_{paper}"
    if refresh or key not in st.session_state:
        st.session_state[key] = _report(ticker, paper, float(risk_budget), int(autopilot_level))
    report = st.session_state[key]

    state = report["state"]
    allocation = report["allocation"]
    rebalance = report["rebalance"]
    governance = report["governance"]

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Positions", state.get("total_positions", 0))
    m2.metric("Portfolio Heat", f"{allocation.get('capital_heat_pct', 0):.1f}%")
    m3.metric("Net Delta", f"{state.get('net_delta', 0):,.2f}")
    m4.metric("Net Theta", f"{state.get('net_theta', 0):,.2f}")
    m5.metric("Rebalance", "Yes" if rebalance.get("rebalance_required") else "No")

    tabs = st.tabs(["📊 Portfolio Brain", "⚖ Allocation", "🔄 Rebalance", "🛡 Hedging", "🎯 Trade Queue", "🏛 Governance", "🧠 Memory", "🤖 AI PM"])

    with tabs[0]:
        st.dataframe(pd.DataFrame(state.get("positions", [])), use_container_width=True, hide_index=True)
        st.json({k: v for k, v in state.items() if k != "positions"})
    with tabs[1]:
        st.json(allocation)
    with tabs[2]:
        st.dataframe(pd.DataFrame(rebalance.get("recommendations", [])), use_container_width=True, hide_index=True)
    with tabs[3]:
        st.dataframe(pd.DataFrame(report.get("hedges", [])), use_container_width=True, hide_index=True)
    with tabs[4]:
        st.dataframe(pd.DataFrame(report.get("trades", [])), use_container_width=True, hide_index=True)
    with tabs[5]:
        st.json(governance.get("guardrails", {}))
        if governance.get("approved"):
            st.markdown("#### Approved / Review Queue")
            st.dataframe(pd.DataFrame(governance.get("approved", [])), use_container_width=True, hide_index=True)
        if governance.get("blocked"):
            st.markdown("#### Blocked")
            st.dataframe(pd.DataFrame(governance.get("blocked", [])), use_container_width=True, hide_index=True)
    with tabs[6]:
        if st.button("Record Current PM Decision", key=f"apm_record_{ticker}"):
            record_pm_decision(st.session_state, ticker, report)
            st.success("Decision recorded in session memory.")
        memory = get_pm_decisions(st.session_state)
        st.dataframe(pd.DataFrame(memory), use_container_width=True, hide_index=True)
    with tabs[7]:
        if st.button("Generate Autonomous PM Commentary", key=f"apm_ai_{ticker}", type="primary"):
            st.session_state[f"apm_ai_text_{ticker}"] = explain_autonomous_pm_report(report)
        st.markdown(st.session_state.get(f"apm_ai_text_{ticker}", "Click the button to generate PM commentary."))
