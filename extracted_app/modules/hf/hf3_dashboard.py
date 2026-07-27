from __future__ import annotations
import pandas as pd
import streamlit as st
from modules.hf.portfolio_construction_os import construct_portfolio, portfolio_to_frame
from modules.hf.capital_allocation_engine import allocate_capital
from modules.hf.risk_budget_engine import calculate_risk_budget, sector_risk_budget
from modules.hf.portfolio_heat_engine import portfolio_heat_report
from modules.hf.factor_exposure_engine import estimate_factor_exposure, factor_frame
from modules.hf.portfolio_optimizer import rebalance_plan
from modules.hf.position_sizing_engine import kelly_fraction, risk_based_position_size

def _sample_candidates(ticker: str) -> list[dict]:
    return [
        {"symbol": ticker.upper(), "sector": "Technology", "thesis_score": 82, "conviction_score": 78, "risk_score": 48, "valuation_score": 63, "momentum_score": 71, "current_weight": 0.03},
        {"symbol": "MSFT", "sector": "Technology", "thesis_score": 76, "conviction_score": 73, "risk_score": 42, "valuation_score": 58, "momentum_score": 66, "current_weight": 0.04},
        {"symbol": "JPM", "sector": "Financials", "thesis_score": 68, "conviction_score": 64, "risk_score": 51, "valuation_score": 70, "momentum_score": 55, "current_weight": 0.02},
        {"symbol": "UNH", "sector": "Healthcare", "thesis_score": 63, "conviction_score": 61, "risk_score": 45, "valuation_score": 62, "momentum_score": 49, "current_weight": 0.01},
        {"symbol": "XOM", "sector": "Energy", "thesis_score": 60, "conviction_score": 58, "risk_score": 54, "valuation_score": 74, "momentum_score": 52, "current_weight": 0.00},
    ]

def render_hf3_portfolio_construction_dashboard(ticker: str = "AAPL", db=None, user: dict | None = None):
    st.subheader("🏗 HF-3 Portfolio Construction & Capital Allocation OS")
    st.caption("Idea ranking → target weights → risk budget → capital allocation → rebalance plan.")

    c1, c2, c3, c4 = st.columns(4)
    portfolio_value = c1.number_input("Portfolio Value", min_value=1000.0, value=1000000.0, step=50000.0, key="hf3_portfolio_value")
    max_positions = c2.number_input("Max Positions", min_value=3, max_value=100, value=25, step=1, key="hf3_max_positions")
    max_name = c3.slider("Max Single Name", 1, 25, 8, key="hf3_max_single") / 100
    max_sector = c4.slider("Max Sector", 5, 60, 30, key="hf3_max_sector") / 100

    candidates = _sample_candidates(ticker)
    result = construct_portfolio(candidates, max_positions=max_positions, max_single_name_weight=max_name, max_sector_weight=max_sector)
    positions = result.get("positions", [])
    alloc = allocate_capital(portfolio_value, positions)
    risk = calculate_risk_budget(positions)
    heat = portfolio_heat_report(positions)
    factors = estimate_factor_exposure(positions)

    tabs = st.tabs(["🎯 Target Portfolio", "💵 Capital Allocation", "⚖ Risk Budget", "🔥 Portfolio Heat", "🧬 Factor Exposure", "🔄 Rebalance Plan", "📐 Position Sizing"])

    with tabs[0]:
        summary = result.get("summary", {})
        a, b, c, d = st.columns(4)
        a.metric("Positions", summary.get("position_count", 0))
        b.metric("Allocated", f"{summary.get('allocated_weight', 0):.1%}")
        c.metric("Cash Reserve", f"{summary.get('cash_reserve', 0):.1%}")
        d.metric("Gross Target", f"{summary.get('target_gross_exposure', 0):.1%}")
        st.dataframe(portfolio_to_frame(result), use_container_width=True, hide_index=True)

    with tabs[1]:
        a, b, c = st.columns(3)
        a.metric("Portfolio Value", f"${alloc['portfolio_value']:,.0f}")
        b.metric("Deployable Capital", f"${alloc['deployable_capital']:,.0f}")
        c.metric("Cash Reserve", f"${alloc['cash_reserve']:,.0f}")
        st.dataframe(pd.DataFrame(alloc["allocations"]), use_container_width=True, hide_index=True)

    with tabs[2]:
        a, b, c = st.columns(3)
        a.metric("Risk Heat", f"{risk['total_risk_heat']:.2f}")
        b.metric("Heat Utilization", f"{risk['heat_utilization']:.1%}")
        c.metric("Status", risk["status"])
        st.dataframe(pd.DataFrame(risk["positions"]), use_container_width=True, hide_index=True)
        sector_df = sector_risk_budget(positions)
        if not sector_df.empty:
            st.dataframe(sector_df, use_container_width=True, hide_index=True)

    with tabs[3]:
        a, b, c = st.columns(3)
        a.metric("Gross Exposure", f"{heat['gross_exposure']:.1%}")
        b.metric("Max Position", f"{heat['max_position_weight']:.1%}")
        c.metric("Max Sector", f"{heat['max_sector_weight']:.1%}")
        if heat["warnings"]:
            for w in heat["warnings"]:
                st.warning(w)
        else:
            st.success("Portfolio heat is within guardrails.")
        st.json(heat["sector_weights"])

    with tabs[4]:
        st.metric("Dominant Factor", factors.get("dominant_factor", "market"))
        ff = factor_frame(factors)
        if not ff.empty:
            st.dataframe(ff, use_container_width=True, hide_index=True)
            st.bar_chart(ff.set_index("factor"))

    with tabs[5]:
        current = [{"symbol": p["symbol"], "current_weight": p.get("current_weight", 0)} for p in positions]
        st.dataframe(rebalance_plan(current, positions), use_container_width=True, hide_index=True)

    with tabs[6]:
        a, b = st.columns(2)
        with a:
            p = st.slider("Win Probability", 1, 99, 55, key="hf3_win_prob") / 100
            wl = st.number_input("Win/Loss Ratio", min_value=0.1, value=1.5, step=0.1, key="hf3_win_loss")
            st.metric("Kelly Fraction", f"{kelly_fraction(p, wl):.1%}")
        with b:
            entry = st.number_input("Entry Price", min_value=0.01, value=100.0, step=1.0, key="hf3_entry")
            stop = st.number_input("Stop Price", min_value=0.01, value=92.0, step=1.0, key="hf3_stop")
            st.json(risk_based_position_size(portfolio_value, entry, stop))
