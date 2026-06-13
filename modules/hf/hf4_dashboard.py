"""
modules/hf/hf4_dashboard.py

Streamlit dashboard for Stock HF-4 Autonomous Equity Portfolio Manager.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.hf.autonomous_equity_pm import autonomous_pm_cycle, decisions_frame
from modules.hf.equity_pm_policy import evaluate_decision_set, DEFAULT_PM_POLICY
from modules.hf.equity_pm_monitor import monitor_portfolio_drift, drift_frame
from modules.hf.equity_pm_rebalance_engine import build_rebalance_orders, orders_frame
from modules.hf.equity_pm_learning_engine import score_pm_outcomes, learning_frame
from modules.hf.equity_pm_ai import explain_pm_cycle


def _sample_candidates(ticker: str) -> list[dict]:
    return [
        {"symbol": ticker.upper(), "sector": "Technology", "thesis_score": 84, "conviction_score": 80, "risk_score": 47, "valuation_score": 61, "momentum_score": 74, "current_weight": 0.03},
        {"symbol": "MSFT", "sector": "Technology", "thesis_score": 78, "conviction_score": 74, "risk_score": 41, "valuation_score": 60, "momentum_score": 69, "current_weight": 0.04},
        {"symbol": "JPM", "sector": "Financials", "thesis_score": 70, "conviction_score": 66, "risk_score": 52, "valuation_score": 72, "momentum_score": 56, "current_weight": 0.02},
        {"symbol": "UNH", "sector": "Healthcare", "thesis_score": 64, "conviction_score": 62, "risk_score": 45, "valuation_score": 63, "momentum_score": 50, "current_weight": 0.01},
        {"symbol": "XOM", "sector": "Energy", "thesis_score": 59, "conviction_score": 57, "risk_score": 55, "valuation_score": 75, "momentum_score": 51, "current_weight": 0.00},
    ]


def render_hf4_autonomous_equity_pm_dashboard(ticker: str = "AAPL", db=None, user: dict | None = None):
    st.subheader("🤖 HF-4 Autonomous Equity Portfolio Manager")
    st.caption("Observe → Score → Decide → Allocate → Rebalance → Monitor → Learn.")

    c1, c2, c3, c4 = st.columns(4)
    portfolio_value = c1.number_input("Portfolio Value", min_value=1000.0, value=1_000_000.0, step=50_000.0, key="hf4_portfolio_value")
    mode = c2.selectbox("PM Mode", ["recommend_only", "approval_required", "simulation"], key="hf4_mode")
    max_name = c3.slider("Max Single Name", 1, 25, 8, key="hf4_max_single") / 100
    max_turnover = c4.slider("Max Turnover / Cycle", 1, 60, 20, key="hf4_max_turnover") / 100

    candidates = _sample_candidates(ticker)
    current_positions = [{"symbol": c["symbol"], "weight": c.get("current_weight", 0)} for c in candidates]
    pm = autonomous_pm_cycle(
        candidates=candidates,
        current_positions=current_positions,
        portfolio_value=portfolio_value,
        mode=mode,
        max_single_name_weight=max_name,
        max_turnover=max_turnover,
    )

    decisions = pm.get("decisions", [])
    policy = evaluate_decision_set(decisions, DEFAULT_PM_POLICY)
    target_positions = pm.get("target_portfolio", {}).get("positions", [])
    drift = monitor_portfolio_drift(current_positions, target_positions)
    orders = build_rebalance_orders(portfolio_value, decisions)
    learning = score_pm_outcomes(decisions)

    tabs = st.tabs([
        "🧠 PM Cycle",
        "🎯 Decisions",
        "🛡 Policy Guardrails",
        "🔄 Rebalance Orders",
        "📡 Drift Monitor",
        "📚 Learning Loop",
        "🤖 PM AI",
    ])

    with tabs[0]:
        a, b, c, d = st.columns(4)
        a.metric("Portfolio Action", pm.get("portfolio_action", "NO_ACTION"))
        b.metric("Turnover", f"{pm.get('turnover_estimate', 0):.1%}")
        c.metric("Guardrails", pm.get("guardrail_status", "UNKNOWN"))
        d.metric("Decisions", len(decisions))
        st.json(pm.get("portfolio_heat", {}))

    with tabs[1]:
        df = decisions_frame(pm)
        if df.empty:
            st.info("No PM decisions generated.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[2]:
        a, b, c = st.columns(3)
        a.metric("Approved", len(policy["approved"]))
        b.metric("Review", len(policy["review"]))
        c.metric("Rejected", len(policy["rejected"]))
        st.dataframe(pd.DataFrame(policy["all"]), use_container_width=True, hide_index=True)

    with tabs[3]:
        odf = orders_frame(orders)
        if odf.empty:
            st.success("No rebalance orders required.")
        else:
            st.warning("Orders are approval-required. No live trading is executed from this dashboard.")
            st.dataframe(odf, use_container_width=True, hide_index=True)

    with tabs[4]:
        a, b = st.columns(2)
        a.metric("Rebalance Needed", "Yes" if drift["rebalance_needed"] else "No")
        b.metric("Drift Threshold", f"{drift['drift_threshold']:.1%}")
        st.dataframe(drift_frame(drift), use_container_width=True, hide_index=True)

    with tabs[5]:
        a, b = st.columns(2)
        a.metric("Accuracy", f"{learning['accuracy']:.1%}")
        b.metric("Evaluated Decisions", learning["evaluated_decisions"])
        lf = learning_frame(learning)
        if not lf.empty:
            st.dataframe(lf, use_container_width=True, hide_index=True)

    with tabs[6]:
        if st.button("Generate PM AI Review", key=f"hf4_ai_{ticker}", type="primary"):
            st.markdown(explain_pm_cycle(pm))
        else:
            st.info("Generate an AI PM review of the autonomous portfolio cycle.")
