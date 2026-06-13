"""
modules/options/options_workstation_ui.py

Expanded options workstation UI that completes the 12-feature roadmap plus
the seven AI advisor workflows.
c2.metric("Move %", f
This file is additive and uses existing:
- modules.options.options_data_service.get_options_chain
- modules.options.options_strategy_engine
- modules.options.options_ai_advisors
- modules.options.options_broker when available
- modules.options_flow.flow_service when available
- modules.smc modules when available
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False

from modules.options.options_data_service import get_options_chain
from modules.options.options_strategy_engine import (
    OptionLeg,
    aggregate_greeks,
    atm_straddle_expected_move,
    build_strategy_from_chain,
    cash_secured_put_candidates,
    covered_call_candidates,
    expected_move,
    legs_to_frame,
    price_grid,
    probability_itm,
    probability_touch,
    screen_options,
    strategy_payoff,
    strategy_template_catalog,
    summarize_strategy,
    volatility_snapshot,
    zero_dte_candidates,
)

from modules.options.options_ai_advisors import (
    ai_options_advisor,
    ai_strategy_generator,
    ai_trade_critic,
    ai_risk_analyzer,
    ai_wheel_assistant,
    ai_covered_call_assistant,
    ai_earnings_options_assistant,
)

from modules.options.options_smart_money_dashboard import render_options_smart_money_dashboard
from modules.options.options_dealer_analytics_dashboard import render_options_dealer_analytics_dashboard
from modules.options.options_volatility_dashboard import render_options_volatility_dashboard
from modules.options.options_ai_institutional_dashboard import render_options_institutional_copilot_dashboard
from modules.options.options_strategy_command_center import render_options_strategy_command_center
from modules.options.options_portfolio_dashboard import render_options_portfolio_dashboard
from modules.options.options_hedge_fund_dashboard import render_options_hedge_fund_dashboard

def _load_chain(ticker: str) -> dict:
    key = f"expanded_chain_{ticker.upper()}"
    if key not in st.session_state:
        with st.spinner(f"Loading options chain for {ticker}…"):
            st.session_state[key] = get_options_chain(ticker)
    return st.session_state[key]


def _spot(data: dict) -> float:
    return float(data.get("spot") or data.get("underlying_price") or data.get("lastTradePrice") or 0.0)


def _all_rows(data: dict) -> pd.DataFrame:
    df = data.get("all_rows", data.get("raw_df", pd.DataFrame()))
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame(df)


def _expiry(data: dict, key: str = "expanded_expiry") -> str:
    exps = data.get("expirations") or []
    if not exps:
        return ""
    return st.selectbox("Expiration", exps, key=key, format_func=lambda x: f"{x} ({_dte(x)}d)")


def _dte(expiry: str) -> int:
    try:
        d = datetime.fromisoformat(str(expiry)[:10]).replace(tzinfo=timezone.utc)
        return max(0, (d - datetime.now(timezone.utc)).days)
    except Exception:
        return 0


def _chain_for_exp(data: dict, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    chain = (data.get("chain") or data.get("chains") or {}).get(expiry, {})
    calls = chain.get("calls", pd.DataFrame())
    puts = chain.get("puts", pd.DataFrame())
    return calls if isinstance(calls, pd.DataFrame) else pd.DataFrame(calls), puts if isinstance(puts, pd.DataFrame) else pd.DataFrame(puts)


def _plot_payoff(spot: float, legs: list[OptionLeg], title: str = "P/L Curve"):
    prices = price_grid(spot, span_pct=0.40)
    pnl = strategy_payoff(legs, prices)
    if PLOTLY:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prices, y=pnl, mode="lines", name="Expiration P/L"))
        fig.add_hline(y=0, line_dash="dash")
        fig.add_vline(x=spot, line_dash="dot", annotation_text="Spot")
        fig.update_layout(title=title, xaxis_title="Underlying Price", yaxis_title="Profit / Loss ($)", height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.line_chart(pd.DataFrame({"Underlying Price": prices, "P/L": pnl}).set_index("Underlying Price"))
    return prices, pnl


def render_strategy_center(ticker: str):
    st.subheader("1. Options Strategy Center")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    st.dataframe(strategy_template_catalog(), use_container_width=True, hide_index=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        market_view = st.selectbox("Market View", ["Bullish", "Bearish", "Neutral", "Volatile"], key="osc_view")
    with c2:
        conviction = st.selectbox("Conviction", ["Low", "Medium", "High"], index=1, key="osc_conviction")
    with c3:
        risk = st.selectbox("Risk Tolerance", ["Conservative", "Moderate", "Aggressive"], index=1, key="osc_risk")
    with c4:
        expiry = _expiry(data, "osc_expiry")
    strategy_map = {
        "Bullish": "Bull Call Spread" if risk != "Aggressive" else "Long Call",
        "Bearish": "Bear Put Spread" if risk != "Aggressive" else "Long Put",
        "Neutral": "Iron Condor",
        "Volatile": "Long Straddle",
    }
    default_strategy = strategy_map.get(market_view, "Bull Call Spread")
    strategy = st.selectbox("Strategy", strategy_template_catalog()["Strategy"].tolist(), index=strategy_template_catalog()["Strategy"].tolist().index(default_strategy), key="osc_strategy")
    width = st.number_input("Wing/Spread Width", min_value=1.0, max_value=max(1.0, spot * 0.20), value=max(1.0, round(spot * 0.03, 0)), step=1.0, key="osc_width")
    legs = build_strategy_from_chain(strategy, data, spot, expiry=expiry, width=width)
    if not legs:
        st.info("No matching contracts found for selected template.")
        return
    st.dataframe(legs_to_frame(legs), use_container_width=True, hide_index=True)
    summary = summarize_strategy(strategy, legs, spot, iv=_avg_iv(data), dte=_dte(expiry))
    _render_summary_metrics(summary)
    _plot_payoff(spot, legs, f"{ticker} {strategy} Payoff")
    if st.button("🤖 Generate AI Strategy Plan", key="ai_strategy_gen"):
        st.info(ai_strategy_generator(ticker, market_view, conviction, risk, {"strategy": strategy, "summary": summary.__dict__, "spot": spot}))


def render_pl_curve_simulator(ticker: str):
    st.subheader("2. P/L Curve Simulator")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    expiry = _expiry(data, "pl_expiry")
    c1, c2, c3 = st.columns(3)
    with c1:
        strategy = st.selectbox("Template", strategy_template_catalog()["Strategy"].tolist(), key="pl_strategy")
    with c2:
        width = st.number_input("Width", 1.0, max(1.0, spot * 0.20), max(1.0, round(spot * 0.03, 0)), 1.0, key="pl_width")
    with c3:
        span = st.slider("Chart Range %", 10, 80, 40, key="pl_span") / 100
    legs = build_strategy_from_chain(strategy, data, spot, expiry=expiry, width=width)
    if not legs:
        st.info("No legs generated.")
        return
    prices = price_grid(spot, span_pct=span)
    pnl = strategy_payoff(legs, prices)
    _plot_payoff(spot, legs, f"{ticker} {strategy} P/L")
    st.dataframe(pd.DataFrame({"Underlying": prices, "P/L": pnl}).round(2), use_container_width=True, hide_index=True)


def render_greeks_dashboard(ticker: str, paper: bool = True):
    st.subheader("3. Greeks Dashboard")
    positions = _get_option_positions(paper)
    if not positions:
        st.info("No broker option positions available. Use sample Greeks below or connect broker.")
        positions = [
            {"option_symbol": f"{ticker} SAMPLE CALL", "underlying": ticker, "qty": 1, "delta": 0.45, "gamma": 0.04, "theta": -0.05, "vega": 0.12, "rho": 0.01},
            {"option_symbol": f"{ticker} SAMPLE PUT", "underlying": ticker, "qty": -1, "delta": -0.32, "gamma": 0.03, "theta": -0.04, "vega": 0.10, "rho": -0.01},
        ]
    totals = aggregate_greeks(positions)
    cols = st.columns(5)
    for c, g in zip(cols, ["delta", "gamma", "theta", "vega", "rho"]):
        c.metric(g.title(), f"{totals.get(g, 0):,.2f}")
    st.dataframe(pd.DataFrame(positions), use_container_width=True, hide_index=True)
    if st.button("🤖 Analyze Greek Risk", key="ai_greek_risk"):
        st.info(ai_risk_analyzer(ticker, positions, totals))


def render_probability_engine(ticker: str):
    st.subheader("4. Options Probability Engine")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    expiry = _expiry(data, "prob_expiry")
    calls, puts = _chain_for_exp(data, expiry)
    opt_type = st.radio("Contract Type", ["Call", "Put"], horizontal=True, key="prob_type")
    df = calls if opt_type == "Call" else puts
    if df.empty:
        st.info("No contracts for selected expiration.")
        return
    strikes = sorted(pd.to_numeric(df["strike"], errors="coerce").dropna().unique().tolist())
    strike = st.selectbox("Strike", strikes, key="prob_strike")
    row = df.iloc[(pd.to_numeric(df["strike"], errors="coerce") - strike).abs().argmin()]
    iv = float(row.get("iv") or row.get("impliedVolatility") or _avg_iv(data) or 0)
    dte = int(row.get("dte") or _dte(expiry))
    p_itm = probability_itm(spot, strike, opt_type, iv, dte)
    p_touch = probability_touch(spot, strike, iv, dte)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Spot", f"${spot:,.2f}")
    c2.metric("IV", f"{iv:.1%}" if iv else "—")
    c3.metric("Prob ITM", f"{p_itm:.1%}" if p_itm is not None else "—")
    c4.metric("Prob Touch", f"{p_touch:.1%}" if p_touch is not None else "—")
    st.caption("Approximation uses Black-Scholes d2 and a doubled touch-probability heuristic.")


def render_expected_move_engine(ticker: str):
    st.subheader("5. Expected Move Analytics")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    expiry = _expiry(data, "em_expiry")
    calls, puts = _chain_for_exp(data, expiry)
    iv = _avg_iv(data)
    dte = _dte(expiry)
    em = expected_move(spot, iv, dte)
    straddle = atm_straddle_expected_move(calls, puts, spot)
    c1, c2, c3, c4 = st.columns(4)
    if "error" not in em:
        c1.metric("IV Expected Move", f"${em['expected_move']:,.2f}")
        move_pct = em.get("expected_move_pct")

        c2.metric(
            "Move %",
            f"{move_pct:.1%}" if move_pct is not None else "N/A"
        )
        c3.metric("68% Low", f"${em['low_68']:,.2f}")
        c4.metric("68% High", f"${em['high_68']:,.2f}")
    if straddle:
        st.markdown("#### ATM Straddle-Implied Move")
        st.json(straddle)
    if st.button("🤖 Earnings Options Assistant", key="ai_earnings_options"):
        st.info(ai_earnings_options_assistant(ticker, em, volatility_snapshot(data), {"expiry": expiry, "spot": spot}))


def render_options_screener(ticker: str):
    st.subheader("6. Options Screener")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    c1, c2 = st.columns(2)
    with c1:
        min_vol = st.number_input("Minimum Volume", 0, 100000, 100, 50, key="screen_min_vol")
    with c2:
        min_oi = st.number_input("Minimum Open Interest", 0, 100000, 250, 50, key="screen_min_oi")
    df = screen_options(data, spot, min_volume=int(min_vol), min_oi=int(min_oi))
    if df.empty:
        st.info("No candidates found.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def render_volatility_center(ticker: str):
    st.subheader("7. Volatility Intelligence Center")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    snap = volatility_snapshot(data)
    if "error" in snap:
        st.info(snap["error"]); return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Median IV", f"{snap['median_iv']:.1%}")
    c2.metric("Mean IV", f"{snap['mean_iv']:.1%}")
    c3.metric("IV Rank Proxy", f"{snap['iv_rank_proxy']:.1%}")
    c4.metric("Contracts", f"{snap['contracts_with_iv']:,}")
    df = _all_rows(data)
    iv_col = "iv" if "iv" in df.columns else "impliedVolatility"
    if iv_col in df.columns:
        st.line_chart(pd.to_numeric(df[iv_col], errors="coerce").dropna().reset_index(drop=True))


def render_wheel_manager(ticker: str):
    st.subheader("8. Wheel Strategy Manager")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    expiry = _expiry(data, "wheel_expiry")
    puts = cash_secured_put_candidates(data, spot, expiry)
    calls = covered_call_candidates(data, spot, 100, expiry)
    tab_puts, tab_calls, tab_ai = st.tabs(["Cash-Secured Puts", "Covered Calls After Assignment", "AI Wheel Plan"])
    with tab_puts:
        st.dataframe(puts, use_container_width=True, hide_index=True)
    with tab_calls:
        st.dataframe(calls, use_container_width=True, hide_index=True)
    with tab_ai:
        if st.button("🤖 Build Wheel Plan", key="ai_wheel_plan"):
            st.info(ai_wheel_assistant(ticker, puts.head(10).to_dict("records"), calls.head(10).to_dict("records"), {"spot": spot, "expiry": expiry}))


def render_covered_call_manager(ticker: str):
    st.subheader("9. Covered Call Manager")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    c1, c2, c3 = st.columns(3)
    with c1:
        shares = st.number_input("Shares Owned", 100, 100000, 100, 100, key="cc_shares")
    with c2:
        cost_basis = st.number_input("Cost Basis", 0.01, 100000.0, float(spot or 1), 0.01, key="cc_basis")
    with c3:
        expiry = _expiry(data, "cc_expiry")
    candidates = covered_call_candidates(data, spot, int(shares), expiry)
    st.dataframe(candidates, use_container_width=True, hide_index=True)
    if st.button("🤖 Covered Call Assistant", key="ai_cc"):
        st.info(ai_covered_call_assistant(ticker, int(shares), float(cost_basis), candidates.head(10).to_dict("records")))


def render_options_paper_trading(ticker: str, paper: bool = True):
    st.subheader("10. Options Paper Trading")
    st.caption("Broker-backed paper options if Alpaca credentials are configured. Otherwise this panel acts as a simulated trade blotter.")
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        broker = AlpacaOptionsBroker(paper=paper)
        account = broker.get_account()
        if account and "error" not in account:
            st.success("Broker connection available.")
            st.json({k: account.get(k) for k in ["account_number", "status", "buying_power", "options_buying_power"] if k in account})
        else:
            st.info("Broker account unavailable. Simulated blotter mode.")
    except Exception as e:
        st.info(f"Broker unavailable: {e}")
    st.markdown("#### Simulated Options Trade Journal")
    if "options_sim_trades" not in st.session_state:
        st.session_state["options_sim_trades"] = []
    with st.form("sim_trade_form"):
        c1, c2, c3, c4 = st.columns(4)
        symbol = c1.text_input("Contract", value=f"{ticker} SIM", key="sim_contract")
        side = c2.selectbox("Side", ["Buy", "Sell"], key="sim_side")
        qty = c3.number_input("Qty", 1, 1000, 1, key="sim_qty")
        price = c4.number_input("Price", 0.01, 9999.0, 1.00, 0.01, key="sim_price")
        if st.form_submit_button("Add Simulated Trade"):
            st.session_state["options_sim_trades"].append({"time": datetime.now(timezone.utc).isoformat(), "contract": symbol, "side": side, "qty": qty, "price": price})
    st.dataframe(pd.DataFrame(st.session_state["options_sim_trades"]), use_container_width=True, hide_index=True)


def render_zero_dte_center(ticker: str):
    st.subheader("11. 0DTE Center")
    data = _load_chain(ticker)
    if "error" in data:
        st.error(data["error"]); return
    spot = _spot(data)
    df = zero_dte_candidates(data, spot)
    if df.empty:
        st.info("No 0DTE/1DTE contracts available for this symbol or provider response.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
    st.warning("0DTE options can move rapidly and may expire worthless. Use strict sizing and defined risk.")


def render_ai_options_advisor(ticker: str, paper: bool = True):
    st.subheader("12. AI Options Advisor Suite")
    data = _load_chain(ticker)
    spot = _spot(data) if "error" not in data else 0
    snap = volatility_snapshot(data) if "error" not in data else {}
    mode = st.selectbox(
        "Advisor",
        [
            "AI Options Advisor",
            "AI Strategy Generator",
            "AI Trade Critic",
            "AI Risk Analyzer",
            "AI Wheel Assistant",
            "AI Covered Call Assistant",
            "AI Earnings Options Assistant",
        ],
        key="advisor_mode",
    )
    if mode == "AI Options Advisor":
        if st.button("Run Advisor", key="run_ai_options_advisor"):
            st.info(ai_options_advisor(ticker, {"spot": spot, "volatility": snap}))
    elif mode == "AI Strategy Generator":
        c1, c2, c3 = st.columns(3)
        view = c1.selectbox("View", ["Bullish", "Bearish", "Neutral", "Volatile"], key="advisor_view")
        conv = c2.selectbox("Conviction", ["Low", "Medium", "High"], key="advisor_conv")
        risk = c3.selectbox("Risk", ["Conservative", "Moderate", "Aggressive"], key="advisor_risk")
        if st.button("Generate Strategy", key="run_ai_strategy"):
            st.info(ai_strategy_generator(ticker, view, conv, risk, {"spot": spot, "volatility": snap}))
    elif mode == "AI Trade Critic":
        strategy = st.text_input("Strategy to critique", "Bull Call Spread", key="critic_strategy")
        if st.button("Critique", key="run_ai_critic"):
            st.info(ai_trade_critic(ticker, strategy, [], {"spot": spot, "volatility": snap}))
    elif mode == "AI Risk Analyzer":
        positions = _get_option_positions(paper)
        totals = aggregate_greeks(positions)
        if st.button("Analyze Risk", key="run_ai_risk"):
            st.info(ai_risk_analyzer(ticker, positions, totals))
    elif mode == "AI Wheel Assistant":
        puts = cash_secured_put_candidates(data, spot).head(10).to_dict("records") if "error" not in data else []
        calls = covered_call_candidates(data, spot).head(10).to_dict("records") if "error" not in data else []
        if st.button("Build Wheel Plan", key="run_ai_wheel"):
            st.info(ai_wheel_assistant(ticker, puts, calls, {"spot": spot}))
    elif mode == "AI Covered Call Assistant":
        shares = st.number_input("Shares", 100, 100000, 100, 100, key="advisor_cc_shares")
        basis = st.number_input("Cost Basis", 0.01, 100000.0, float(spot or 1), 0.01, key="advisor_cc_basis")
        calls = covered_call_candidates(data, spot, int(shares)).head(10).to_dict("records") if "error" not in data else []
        if st.button("Analyze Covered Calls", key="run_ai_cc"):
            st.info(ai_covered_call_assistant(ticker, int(shares), float(basis), calls))
    else:
        em = expected_move(spot, snap.get("median_iv"), 30) if spot and snap.get("median_iv") else {}
        if st.button("Analyze Earnings Setup", key="run_ai_earnings"):
            st.info(ai_earnings_options_assistant(ticker, em, snap, {"spot": spot}))


def render_full_options_workstation(ticker: str, paper: bool = True):
    """Render the advanced options workstation using grouped workspaces.

    This avoids the previous 12+ flat-tab layout that overflowed smaller screens.
    """
    workspace_tabs = st.tabs([
        "📊 Strategy",
        "📈 Analytics",
        "💰 Income",
        "🐋 Smart Money",
        "🎧 Dealer",
        "🧪 Trading Lab",
        "🤖 AI Copilot",
        "🧠 Strategy Command",
        "🏦 Portfolio",
        "🏛 Hedge Fund",
    ])

    with workspace_tabs[0]:
        strategy_tabs = st.tabs([
            "Strategy Center",
            "P/L Curve",
            "Probabilities",
        ])
        with strategy_tabs[0]:
            render_strategy_center(ticker)
        with strategy_tabs[1]:
            render_pl_curve_simulator(ticker)
        with strategy_tabs[2]:
            render_probability_engine(ticker)

    with workspace_tabs[1]:
        analytics_tabs = st.tabs([
            "Greeks",
            "Expected Move",
            "Volatility",
            "Volatility Suite",
        ])
        with analytics_tabs[0]:
            render_greeks_dashboard(ticker, paper)
        with analytics_tabs[1]:
            render_expected_move_engine(ticker)
        with analytics_tabs[2]:
            render_volatility_center(ticker)
        with analytics_tabs[3]:
            render_options_volatility_dashboard(ticker)

    with workspace_tabs[2]:
        income_tabs = st.tabs([
            "Wheel Manager",
            "Covered Calls",
        ])
        with income_tabs[0]:
            render_wheel_manager(ticker)
        with income_tabs[1]:
            render_covered_call_manager(ticker)

    with workspace_tabs[3]:
        render_options_smart_money_dashboard(ticker)

    with workspace_tabs[4]:
        render_options_dealer_analytics_dashboard(ticker)

    with workspace_tabs[5]:
        trading_tabs = st.tabs([
            "Screener",
            "Paper Trading",
            "0DTE",
        ])
        with trading_tabs[0]:
            render_options_screener(ticker)
        with trading_tabs[1]:
            render_options_paper_trading(ticker, paper)
        with trading_tabs[2]:
            render_zero_dte_center(ticker)

    with workspace_tabs[6]:
        ai_tabs = st.tabs([
            "Advisor Suite",
            "Institutional Copilot",
        ])
        with ai_tabs[0]:
            render_ai_options_advisor(ticker, paper)
        with ai_tabs[1]:
            render_options_institutional_copilot_dashboard(ticker)

    with workspace_tabs[7]:
        render_options_strategy_command_center(ticker)
        
    with workspace_tabs[8]:
        render_options_portfolio_dashboard(ticker, paper)

    with workspace_tabs[9]:
        render_options_hedge_fund_dashboard(ticker, paper)

def _avg_iv(data: dict) -> float | None:
    snap = volatility_snapshot(data)
    if "error" not in snap:
        return snap.get("median_iv")
    return None


def _render_summary_metrics(summary):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Net Debit/Credit", f"${summary.net_debit_credit:,.2f}")
    c2.metric("Max Profit", str(summary.max_profit))
    c3.metric("Max Loss", str(summary.max_loss))
    c4.metric("Risk/Reward", str(summary.risk_reward or "—"))
    c5.metric("Prob Profit", f"{summary.probability_profit:.1%}" if summary.probability_profit is not None else "—")
    for note in summary.notes:
        st.caption(note)


def _get_option_positions(paper: bool = True) -> list[dict]:
    try:
        from modules.options.options_broker import AlpacaOptionsBroker
        broker = AlpacaOptionsBroker(paper=paper)
        pos = broker.get_positions()
        if pos:
            return [p.__dict__ if hasattr(p, "__dict__") else dict(p) for p in pos]
    except Exception:
        pass
    return []
