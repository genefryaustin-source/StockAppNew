"""
modules/options/options_portfolio_dashboard.py

Phase 6 — Portfolio & Risk Command Center dashboard.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

from modules.options.options_portfolio_engine import load_portfolio_positions, positions_frame
from modules.options.options_portfolio_analytics import summarize_options_portfolio, exposure_by_underlying, exposure_by_strategy
from modules.options.options_portfolio_exposure import calculate_exposure_map
from modules.options.options_portfolio_risk_engine import score_portfolio_risk
from modules.options.options_portfolio_margin_engine import estimate_margin_requirement, load_account_snapshot
from modules.options.options_portfolio_stress_test import run_portfolio_stress_test, stress_test_frame
from modules.options.options_portfolio_scenario_engine import build_scenario_readouts, classify_portfolio_scenario_bias
from modules.options.options_position_sizing_engine import calculate_position_size, kelly_fraction
from modules.options.options_portfolio_optimizer import generate_portfolio_optimization_suggestions
from modules.options.options_portfolio_ai import explain_portfolio_risk


def _fmt_money(v: Any) -> str:
    try:
        return f"${float(v):,.0f}"
    except Exception:
        return "$0"


def _fmt_num(v: Any) -> str:
    try:
        return f"{float(v):,.2f}"
    except Exception:
        return "0.00"


def _load_phase6_report(ticker: str, paper: bool = True) -> dict[str, Any]:
    positions = load_portfolio_positions(ticker=ticker, paper=paper)
    summary = summarize_options_portfolio(positions)
    exposure = calculate_exposure_map(positions)
    risk = score_portfolio_risk(summary, exposure)
    account = load_account_snapshot(paper=paper)
    margin = estimate_margin_requirement(positions, account)
    stress = run_portfolio_stress_test(positions)
    scenarios = build_scenario_readouts(stress)
    bias = classify_portfolio_scenario_bias(stress)
    optimizations = generate_portfolio_optimization_suggestions(summary, risk, exposure)
    return {
        "ticker": ticker.upper(),
        "positions": positions,
        "summary": summary,
        "exposure": exposure,
        "risk": risk,
        "account": account,
        "margin": margin,
        "stress": stress,
        "scenarios": scenarios,
        "scenario_bias": bias,
        "optimizations": optimizations,
    }


def render_options_portfolio_dashboard(ticker: str, paper: bool = True):
    st.subheader("🏦 Portfolio Command Center")
    st.caption("Portfolio-level options exposure, Greeks, stress tests, margin, sizing, optimization, and AI risk review.")

    cache_key = f"phase6_portfolio_report_{ticker}_{paper}"
    c1, c2 = st.columns([1, 5])
    with c1:
        refresh = st.button("↺ Refresh Portfolio", key=f"phase6_portfolio_refresh_{ticker}_{paper}", use_container_width=True)
    if refresh or cache_key not in st.session_state:
        with st.spinner("Building options portfolio risk report…"):
            st.session_state[cache_key] = _load_phase6_report(ticker, paper)
    report = st.session_state.get(cache_key, _load_phase6_report(ticker, paper))

    summary = report.get("summary", {})
    exposure = report.get("exposure", {})
    risk = report.get("risk", {})
    margin = report.get("margin", {})
    positions = report.get("positions", [])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Positions", int(summary.get("position_count", 0)))
    m2.metric("Total Exposure", _fmt_money(summary.get("total_market_value", 0)))
    m3.metric("Unrealized P&L", _fmt_money(summary.get("total_unrealized_pnl", 0)))
    m4.metric("Risk", f"{risk.get('label', 'Unknown')} ({risk.get('score', 0)}/100)")
    m5.metric("Capital Utilization", f"{float(margin.get('capital_utilization', 0))*100:.1f}%")

    tabs = st.tabs([
        "📊 Overview",
        "⚖ Risk Exposure",
        "🧪 Stress Testing",
        "📈 Greeks",
        "💰 Income",
        "🏦 Margin",
        "🎯 Position Sizing",
        "🧠 Portfolio AI",
    ])

    with tabs[0]:
        st.markdown("#### Portfolio Positions")
        df = positions_frame(positions)
        if df.empty:
            st.info("No options portfolio positions detected. Connect broker positions or add simulated trades first.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown("#### Exposure by Underlying")
        by_u = exposure_by_underlying(positions)
        if not by_u.empty:
            st.dataframe(by_u, use_container_width=True, hide_index=True)

    with tabs[1]:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Net Delta", _fmt_num(exposure.get("net_delta")))
        c2.metric("Net Gamma", _fmt_num(exposure.get("net_gamma")))
        c3.metric("Net Theta", _fmt_num(exposure.get("net_theta")))
        c4.metric("Net Vega", _fmt_num(exposure.get("net_vega")))
        c5.metric("Net Rho", _fmt_num(exposure.get("net_rho")))
        st.markdown("#### Risk Flags")
        for flag in risk.get("flags", []):
            st.warning(flag) if risk.get("label") in {"High", "Critical"} else st.info(flag)
        st.markdown("#### Optimization Suggestions")
        st.dataframe(pd.DataFrame(report.get("optimizations", [])), use_container_width=True, hide_index=True)

    with tabs[2]:
        st.markdown("#### Stress Test Results")
        stress_df = stress_test_frame(positions)
        if stress_df.empty:
            st.info("No stress-test data available.")
        else:
            st.dataframe(stress_df, use_container_width=True, hide_index=True)
            chart_df = stress_df.set_index("scenario")[["estimated_pnl"]]
            st.bar_chart(chart_df)
        st.markdown("#### Scenario Bias")
        st.metric("Portfolio Scenario Bias", report.get("scenario_bias", "Unknown"))
        st.info(report.get("scenarios", {}).get("summary", "No scenario readout."))

    with tabs[3]:
        st.markdown("#### Aggregate Greeks")
        greeks_df = pd.DataFrame([{
            "Delta": exposure.get("net_delta", 0),
            "Gamma": exposure.get("net_gamma", 0),
            "Theta": exposure.get("net_theta", 0),
            "Vega": exposure.get("net_vega", 0),
            "Rho": exposure.get("net_rho", 0),
        }])
        st.dataframe(greeks_df, use_container_width=True, hide_index=True)
        by_u = exposure_by_underlying(positions)
        if not by_u.empty:
            st.markdown("#### Greeks by Underlying")
            st.dataframe(by_u, use_container_width=True, hide_index=True)

    with tabs[4]:
        st.markdown("#### Income Portfolio")
        st.metric("Monthly Theta Income Projection", _fmt_money(summary.get("income_estimate_monthly", 0)))
        by_strategy = exposure_by_strategy(positions)
        if not by_strategy.empty:
            st.dataframe(by_strategy, use_container_width=True, hide_index=True)
        st.caption("Income estimate is a theta-based approximation and should be reviewed against actual premium capture.")

    with tabs[5]:
        st.markdown("#### Margin Analysis")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Estimated Margin", _fmt_money(margin.get("estimated_margin_requirement", 0)))
        c2.metric("Largest Position Margin", _fmt_money(margin.get("largest_position_margin", 0)))
        c3.metric("Buying Power", _fmt_money(margin.get("buying_power", 0)))
        c4.metric("Risk Utilization", margin.get("risk_utilization_label", "Unknown"))
        st.json(margin)

    with tabs[6]:
        st.markdown("#### Position Sizing Calculator")
        account_equity = st.number_input("Account Equity", min_value=1000.0, value=float(margin.get("equity") or 100000.0), step=1000.0, key=f"phase6_equity_{ticker}")
        risk_pct = st.slider("Max Risk Per Trade", 0.0025, 0.10, 0.02, 0.0025, key=f"phase6_risk_pct_{ticker}")
        max_loss = st.number_input("Max Loss Per Contract", min_value=1.0, value=250.0, step=25.0, key=f"phase6_max_loss_{ticker}")
        sizing = calculate_position_size(account_equity, risk_pct, max_loss)
        st.dataframe(pd.DataFrame([sizing]), use_container_width=True, hide_index=True)
        st.markdown("#### Kelly Fraction")
        p = st.slider("Win Probability", 0.05, 0.95, 0.55, 0.01, key=f"phase6_win_prob_{ticker}")
        avg_win = st.number_input("Average Win", min_value=1.0, value=400.0, step=25.0, key=f"phase6_avg_win_{ticker}")
        avg_loss = st.number_input("Average Loss", min_value=1.0, value=250.0, step=25.0, key=f"phase6_avg_loss_{ticker}")
        st.metric("Capped Kelly Fraction", f"{kelly_fraction(p, avg_win, avg_loss)*100:.1f}%")

    with tabs[7]:
        st.markdown("#### Portfolio AI Risk Review")
        if st.button("Generate Portfolio AI Review", key=f"phase6_portfolio_ai_{ticker}", type="primary"):
            with st.spinner("Generating portfolio risk commentary…"):
                st.session_state[f"phase6_ai_text_{ticker}"] = explain_portfolio_risk(report)
        if st.session_state.get(f"phase6_ai_text_{ticker}"):
            st.markdown(st.session_state[f"phase6_ai_text_{ticker}"])
        else:
            st.info("Click the button to generate portfolio-level AI risk commentary.")
