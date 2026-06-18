"""
modules/options/options_ui.py

Options Trading — Full UI with 5 components:
  📊 Chain Viewer      — live chain, Greeks, IV surface
  🎯 Order Ticket      — buy/sell calls/puts via Alpaca
  📈 Positions         — open options P&L, Greeks, DTE
  🏗 Strategy Builder  — multi-leg payoff diagrams
  💰 P&L Calculator    — interactive payoff at expiry

Add to app.py:
    elif page == "Options Trading":
        from modules.options.options_ui import render_options_trading_page
        render_options_trading_page(db, user)
"""
from __future__ import annotations
import math
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY = True
except ImportError:
    PLOTLY = False

from modules.options.options_data_service import get_options_chain, get_iv_surface
from modules.options.options_ai import (
    generate_trade_thesis,
    recommend_strategy,
    scan_portfolio_risk,
    options_qa,
    build_chain_summary,
    interpret_flow_alerts,
    detect_unusual_contracts,
)
from modules.options.options_broker import AlpacaOptionsBroker, OptionsOrderRequest
from modules.options.options_models import ensure_tables, save_order, get_order_history
from modules.options.options_workstation_ui import render_full_options_workstation
from modules.options.options_intelligence_dashboard import render_options_intelligence_dashboard
from modules.options.options_flow_intelligence_dashboard import render_flow_intelligence_dashboard
from modules.options.options_market_maker_intelligence_dashboard import (render_market_maker_intelligence_dashboard,)
from modules.options.options_volatility_intelligence_dashboard import (
    render_volatility_intelligence_dashboard,
)
from modules.options.options_strategy_factory_dashboard import (
    render_strategy_factory_dashboard,
)
from modules.options.options_portfolio_risk_dashboard import (
    render_portfolio_risk_dashboard,
)
from modules.options.options_stress_testing_dashboard import (
    render_stress_testing_dashboard,
)
from modules.options.options_greeks_exposure_dashboard import (
    render_greeks_exposure_dashboard,
)
from modules.options.options_risk_guardrails_dashboard import render_risk_guardrails_dashboard
from modules.options.options_portfolio_construction_dashboard import (
    render_portfolio_construction_dashboard,
)
from modules.options.options_execution_quality_dashboard import (
    render_execution_quality_dashboard,
)
from modules.options.options_liquidity_dashboard import (
    render_liquidity_intelligence_dashboard,
)

from modules.options.options_position_sizing_dashboard import (
    render_position_sizing_dashboard,
)
from modules.options.options_capital_allocation_dashboard import (
    render_capital_allocation_dashboard,
)
from modules.options.options_trade_optimization_dashboard import (
    render_trade_optimization_dashboard,
)
from modules.options.options_portfolio_hedging_dashboard import (
    render_portfolio_hedging_dashboard,
)

from modules.options.options_dynamic_risk_adjustment_dashboard import (
    render_dynamic_risk_adjustment_dashboard,
)

from modules.options.options_institutional_trade_planner_dashboard import (
    render_institutional_trade_planner_dashboard,
)

from modules.options.options_cross_asset_exposure_dashboard import (
    render_cross_asset_exposure_dashboard,
)
from modules.options.options_autonomous_portfolio_manager_dashboard import (
    render_autonomous_portfolio_manager_dashboard,
)
from modules.options.options_roll_dashboard import (
    render_roll_dashboard,
)
from modules.options.options_position_lifecycle_dashboard import (
    render_position_lifecycle_dashboard,
)

from modules.options.options_income_dashboard import (
    render_income_dashboard,
)

from modules.options.options_assignment_dashboard import (
    render_assignment_dashboard,
)
from modules.options.options_portfolio_command_dashboard import (
    render_portfolio_command_center_dashboard,
)

from modules.options.options_institutional_operations_dashboard import (
    render_institutional_operations_dashboard,
)

from modules.options.options_wheel_dashboard import (
    render_wheel_dashboard,
)
from modules.options.options_covered_call_factory_dashboard import (
    render_covered_call_factory_dashboard,
)
from modules.options.options_cash_secured_put_factory_dashboard import (
    render_cash_secured_put_factory_dashboard,
)
from modules.options.options_income_command_dashboard import (
    render_income_command_center_dashboard,
)
from modules.options.options_volatility_surface_dashboard import (
    render_volatility_surface_dashboard,
)
from modules.options.options_volatility_regime_dashboard import (
    render_volatility_regime_dashboard,
)
from modules.options.options_skew_dashboard import (
    render_skew_dashboard,
)
from modules.options.options_term_structure_dashboard import (
    render_term_structure_dashboard,
)
from modules.options.options_volatility_command_center_dashboard import (
    render_volatility_command_center_dashboard,
)
from modules.options.options_dealer_positioning_dashboard import (
    render_dealer_positioning_dashboard,
)
from modules.options.options_gamma_exposure_dashboard import (
    render_gamma_exposure_dashboard,
)
from modules.options.options_liquidity_provider_dashboard import (
    render_liquidity_provider_dashboard,
)
from modules.options.options_dealer_hedging_flow_dashboard import (
    render_dealer_hedging_flow_dashboard,
)
from modules.options.options_market_maker_command_center_dashboard import (
    render_market_maker_command_center_dashboard,
)
from modules.options.options_portfolio_optimization_ai_dashboard import (
    render_portfolio_optimization_ai_dashboard,
)
from modules.options.options_autonomous_trade_selection_dashboard import (
    render_autonomous_trade_selection_dashboard,
)

from modules.options.options_autonomous_risk_rebalancing_dashboard import (
    render_autonomous_risk_rebalancing_dashboard,
)
from modules.options.options_autonomous_income_management_dashboard import (
    render_autonomous_income_management_dashboard,
)

from modules.options.options_institutional_cio_dashboard import (
    render_institutional_options_cio_dashboard,
)




# ── Colour palette ─────────────────────────────────────────────────────────────
CALL_CLR = "#1D9E75"
PUT_CLR  = "#E24B4A"
NAVY     = "#1F3864"
BLUE     = "#2E75B6"


def render_options_trading_page(db, user: dict):
    tenant_id = (user or {}).get("tenant_id", "default_tenant")
    user_id   = (user or {}).get("user_id", "")

    st.header("⚡ Options Trading")
    st.caption("Live chain · Order ticket · Positions · Strategy builder · P&L calculator")

    col_sym, col_mode = st.columns([3, 2])
    with col_sym:
        ticker = st.text_input("Underlying symbol", value="SPY",
                                key="opt_ticker", placeholder="SPY, AAPL, NVDA…"
                               ).upper().strip()
    with col_mode:
        st.write("")
        paper = st.toggle("📄 Paper Trading", value=True, key="opt_paper",
                          help="Paper = Alpaca paper account. Disable for live trading.")
        if not paper:
            st.warning("⚠️ LIVE TRADING MODE — real money orders")

    if not ticker:
        st.info("Enter a ticker to begin.")
        return

    # ============================================================================
    # OPTIONS OPERATING SYSTEM NAVIGATION
    # ============================================================================

    section = st.radio(
        "Options Section",
        [
            "📈 Trading",
            "🧠 Intelligence",
            "🏛 Institutional",
            "⚙️ Execution",
        ],
        horizontal=True,
        key="options_section",
        label_visibility="collapsed",
    )

    chain_key = f"opt_chain_{ticker}"
    chain_data = st.session_state.get(chain_key)

    if not chain_data:
        with st.spinner(f"Loading options chain for {ticker}..."):
            chain_data = get_options_chain(ticker)
            st.session_state[chain_key] = chain_data

    # ============================================================================
    # TRADING WORKSPACE
    # ============================================================================

    if section == "📈 Trading":

        workspace = st.radio(
            "Workspace",
            [
                "📊 Chain",
                "🎯 Trade",
                "📈 Positions",
                "🏗 Builder",
                "💰 P&L",
            ],
            horizontal=True,
            label_visibility="collapsed",
        )

        if workspace == "📊 Chain":
            _render_chain_viewer(ticker)

        elif workspace == "🎯 Trade":
            _render_order_ticket(
                db,
                ticker,
                tenant_id,
                user_id,
                paper,
            )

        elif workspace == "📈 Positions":
            _render_positions(
                db,
                tenant_id,
                paper,
            )

        elif workspace == "🏗 Builder":
            _render_strategy_builder(ticker)

        elif workspace == "💰 P&L":
            _render_pnl_calculator(ticker)



    # ============================================================================
    # INTELLIGENCE WORKSPACE
    # ============================================================================

    elif section == "🧠 Intelligence":

        workspace = st.radio(
            "Analysis Workspace",
            [
                "🤖 AI",
                "🧠 Intelligence",
                "🌊 Flow",
                "🏦 Market Maker",
                "🏛 Dealer Positioning",
                "⚛ Gamma Exposure",
                "🌊 Dealer Hedging Flow",
                "🏪 Liquidity Providers",
                "🏦 MM Command",
                "🌪 Volatility",
                "🌋 Vol Surface",
                "📡 Vol Regime",
                "🧱 Term Structure",
                "⚡ Skew",
                "🏦 Vol Command",
            ],
            label_visibility="collapsed"
        )

        if workspace == "🤖 AI":
            _render_ai_analysis(
                ticker,
                paper,
            )

        elif workspace == "🧠 Intelligence":
            render_options_intelligence_dashboard(
                ticker,
                chain_data,
            )

        elif workspace == "🌊 Flow":
            render_flow_intelligence_dashboard(
                ticker,
                chain_data,
            )

        elif workspace == "🏦 Market Maker":
            render_market_maker_intelligence_dashboard(
                ticker,
                chain_data,
            )

        elif workspace == "🏛 Dealer Positioning":
            render_dealer_positioning_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "⚛ Gamma Exposure":
            render_gamma_exposure_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "🌊 Dealer Hedging Flow":
            render_dealer_hedging_flow_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )



        elif workspace == "🏪 Liquidity Providers":
            render_liquidity_provider_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "🏦 MM Command":
            render_market_maker_command_center_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "🌪 Volatility":
            render_volatility_intelligence_dashboard(
                ticker,
                chain_data,
            )

        elif workspace == "🌋 Vol Surface":
            render_volatility_surface_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "📡 Vol Regime":
            render_volatility_regime_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )
        elif workspace == "🧱 Term Structure":
            render_term_structure_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "⚡ Skew":
            render_skew_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )
        elif workspace == "🏦 Vol Command":
            render_volatility_command_center_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )



    # ============================================================================
    # INSTITUTIONAL WORKSPACE
    # ============================================================================

    elif section == "🏛 Institutional":

        workspace = st.radio(
            "Institutional Workspace",
            [
                "🏦 Command Center",
                "🏢 Operations",
                "🧠 Portfolio Optimization AI",
                "🤖 Trade Selection",
                "🧭 Risk Rebalancing",
                "💰 Auto Income",
                "🏛 CIO Dashboard",
                "💰 Income Command",
                "🛡 Portfolio Risk",
                "🔥 Stress Testing",
                "📈 Greeks",
                "🚦 Guardrails",
                "🏗 Construction",
                "🔄 Lifecycle",
                "🔁 Rolling",
                "💵 Income",
                "🛞 Wheel",
                "🏭 Covered Call Factory",
                "🏦 Cash Secured Put Factory",
                "⏳ Assignment",
                "🛡 Hedging",
                "🧭 Dynamic Risk",
                "🌐 Cross Asset",
                "🤖 Auto Manager",
                "🏭 Strategy Factory",
                "🚀 Workstation",
            ],
            horizontal=True,
            key="options_institutional_workspace",
            label_visibility="collapsed",
        )

        if workspace == "🏦 Command Center":
            render_portfolio_command_center_dashboard(
                ticker=ticker,
                paper=paper,
            )
        elif workspace == "🏢 Operations":
            render_institutional_operations_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🧠 Portfolio Optimization AI":
            render_portfolio_optimization_ai_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🤖 Trade Selection":
            render_autonomous_trade_selection_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🧭 Risk Rebalancing":
            render_autonomous_risk_rebalancing_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "💰 Auto Income":
            render_autonomous_income_management_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🏛 CIO Dashboard":
            render_institutional_options_cio_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "💰 Income Command":
            render_income_command_center_dashboard(
                ticker=ticker,
                paper=paper,
            )
        elif workspace == "🛡 Portfolio Risk":
            render_portfolio_risk_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🔥 Stress Testing":
            render_stress_testing_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "📈 Greeks":
            render_greeks_exposure_dashboard(
                ticker=ticker,
                paper=paper,
            )
        elif workspace == "🚦 Guardrails":
            render_risk_guardrails_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🏗 Construction":
            render_portfolio_construction_dashboard(
                ticker=ticker,
                paper=paper,
            )
        elif workspace == "🔄 Lifecycle":
            render_position_lifecycle_dashboard(
                ticker=ticker,
                paper=paper,
        )

        elif workspace == "🔁 Rolling":
            render_roll_dashboard(
                ticker=ticker,
                paper=paper,
            )
        elif workspace == "💵 Income":
            render_income_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🛞 Wheel":
            render_wheel_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🏭 Covered Call Factory":
            render_covered_call_factory_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🏦 Cash Secured Put Factory":
            render_cash_secured_put_factory_dashboard(
                ticker=ticker,
                paper=paper,
                chain_data=chain_data,
            )

        elif workspace == "⏳ Assignment":
            render_assignment_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🛡 Hedging":
            render_portfolio_hedging_dashboard(
                ticker=ticker,
                paper=paper,
            )



        elif workspace == "🧭 Dynamic Risk":
            render_dynamic_risk_adjustment_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🌐 Cross Asset":
            render_cross_asset_exposure_dashboard()

        elif workspace == "🤖 Auto Manager":
            render_autonomous_portfolio_manager_dashboard(
                ticker=ticker,
                paper=paper,
            )

        elif workspace == "🏭 Strategy Factory":
            render_strategy_factory_dashboard(
                ticker,
                chain_data,
            )

        elif workspace == "🚀 Workstation":
            render_full_options_workstation(
                ticker,
                paper,
            )


    elif section == "⚙️ Execution":

        workspace = st.radio(
            "Execution Workspace",
            [
                "⚙️ Execution Quality",
                "💧 Liquidity",
                "📏 Position Sizing",
                "💼 Capital Allocation",
                "🎯 Trade Optimization",
                "📋 Trade Planner",
            ],
            horizontal=True,
            key="options_execution_workspace",
            label_visibility="collapsed",
        )

        if workspace == "⚙️ Execution Quality":
            render_execution_quality_dashboard(
                db=db,
                tenant_id=tenant_id,
            )

        elif workspace == "💧 Liquidity":
            render_liquidity_intelligence_dashboard(
                ticker=ticker,
                chain_data=chain_data,
            )

        elif workspace == "📏 Position Sizing":
            render_position_sizing_dashboard()


        elif workspace == "💼 Capital Allocation":
            render_capital_allocation_dashboard()

        elif workspace == "🎯 Trade Optimization":
            render_trade_optimization_dashboard()

        elif workspace == "📋 Trade Planner":
            render_institutional_trade_planner_dashboard()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — CHAIN VIEWER
# ══════════════════════════════════════════════════════════════════════════════

def _render_chain_viewer(ticker: str):
    st.subheader(f"📊 Options Chain — {ticker}")
    st.caption("Live chain from MarketData.app · Greeks · IV · Open Interest")

    cache_key = f"opt_chain_{ticker}"
    col_r, col_f = st.columns([1, 4])
    with col_r:
        if st.button("↺ Refresh", key="chain_refresh"):
            if cache_key in st.session_state:
                del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner(f"Loading options chain for {ticker}…"):
            st.session_state[cache_key] = get_options_chain(ticker)

    data = st.session_state[cache_key]

    if "error" in data:
        st.error(data["error"])
        return

    expirations = data.get("expirations", [])
    if not expirations:
        st.warning("No expirations found.")
        return

    # ── Expiry selector ───────────────────────────────────────
    with col_f:
        sel_exp = st.selectbox(
            "Expiration",
            expirations,
            format_func=lambda x: f"{x}  ({_dte(x)}d)",
            key="chain_exp",
        )

    chain = data["chain"].get(sel_exp, {})
    calls = chain.get("calls", pd.DataFrame())
    puts  = chain.get("puts",  pd.DataFrame())

    # ── Summary metrics ───────────────────────────────────────
    all_rows = data.get("all_rows", pd.DataFrame())
    if not all_rows.empty:
        total_vol = int(all_rows["volume"].fillna(0).sum())
        total_oi  = int(all_rows["open_interest"].fillna(0).sum())
        avg_iv    = all_rows["iv"].dropna().mean()
        pcr = (
            all_rows[all_rows["type"]=="put"]["volume"].fillna(0).sum() /
            max(1, all_rows[all_rows["type"]=="call"]["volume"].fillna(0).sum())
        )
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Expirations",  len(expirations))
        c2.metric("Total Volume", f"{total_vol:,}")
        c3.metric("Open Interest",f"{total_oi:,}")
        c4.metric("Avg IV",       f"{avg_iv*100:.1f}%" if avg_iv else "—")
        c5.metric("Put/Call Vol", f"{pcr:.2f}",
                  delta="Bearish" if pcr > 1.2 else "Bullish" if pcr < 0.7 else "Neutral",
                  delta_color="inverse" if pcr > 1.2 else "normal" if pcr < 0.7 else "off")

    # ── Calls / Puts tabs ─────────────────────────────────────
    tab_c, tab_p, tab_surface = st.tabs(["Calls", "Puts", "IV Surface"])

    display_cols = ["strike","last","bid","ask","volume","open_interest","iv","delta","gamma","theta","vega","option_symbol"]

    with tab_c:
        if not calls.empty:
            _render_chain_table(calls, "call", display_cols)
        else:
            st.info("No call data for this expiry.")

    with tab_p:
        if not puts.empty:
            _render_chain_table(puts, "put", display_cols)
        else:
            st.info("No put data for this expiry.")

    with tab_surface:
        _render_iv_surface(ticker)


def _render_chain_table(df: pd.DataFrame, opt_type: str, cols: list):
    color = CALL_CLR if opt_type == "call" else PUT_CLR
    show = [c for c in cols if c in df.columns]
    labels = {
        "strike":"Strike","last":"Last","bid":"Bid","ask":"Ask",
        "volume":"Volume","open_interest":"OI","iv":"IV",
        "delta":"Δ Delta","gamma":"Γ Gamma","theta":"Θ Theta",
        "vega":"V Vega","option_symbol":"Contract"
    }
    display = df[show].rename(columns=labels)
    # Format
    fmt = {}
    for c in display.columns:
        if c in ("Strike","Last","Bid","Ask"):     fmt[c] = "${:.2f}"
        elif c in ("IV",):                          fmt[c] = "{:.1%}"
        elif c in ("Δ Delta","Γ Gamma","Θ Theta","V Vega"): fmt[c] = "{:.4f}"
        elif c in ("Volume","OI"):                  fmt[c] = "{:,.0f}"
    styled = display.style.format(fmt, na_rep="—")
    st.dataframe(styled, use_container_width=True, hide_index=True, height=380)


def _render_iv_surface(ticker: str):
    st.markdown("#### IV Surface (Calls)")
    if not PLOTLY:
        st.info("Install plotly for IV surface chart.")
        return
    with st.spinner("Building IV surface…"):
        pivot = get_iv_surface(ticker)
    if pivot.empty:
        st.info("Not enough data for IV surface.")
        return
    try:
        dte_labels    = [str(d) for d in pivot.index.tolist()]
        strike_labels = [str(s) for s in pivot.columns.tolist()]
        z_vals        = (pivot.values * 100).tolist()

        fig = go.Figure(go.Surface(
            z=z_vals,
            x=strike_labels,
            y=dte_labels,
            colorscale="RdYlGn_r",
            colorbar=dict(title="IV %", ticksuffix="%"),
        ))
        fig.update_layout(
            scene=dict(
                xaxis_title="Strike",
                yaxis_title="DTE",
                zaxis_title="IV %",
                bgcolor="#161B22",
            ),
            paper_bgcolor="#0F1117",
            height=450,
            margin=dict(l=0,r=0,t=20,b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info(f"IV surface unavailable: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — ORDER TICKET
# ══════════════════════════════════════════════════════════════════════════════

def _render_order_ticket(db, ticker: str, tenant_id: str, user_id: str, paper: bool):
    st.subheader(f"🎯 Options Order Ticket — {ticker}")
    mode_str = "📄 Paper" if paper else "⚡ Live"
    st.caption(f"Mode: **{mode_str}** · Alpaca options API · OCC contract format")

    # Load chain for contract selector
    chain_key = f"opt_chain_{ticker}"
    if chain_key not in st.session_state:
        with st.spinner("Loading chain…"):
            st.session_state[chain_key] = get_options_chain(ticker)

    data = st.session_state.get(chain_key, {})
    expirations = data.get("expirations", [])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Contract Selection")
        opt_type = st.radio("Type", ["Call", "Put"], horizontal=True,
                            key="ot_type")

        if expirations:
            expiry = st.selectbox("Expiration", expirations,
                                   format_func=lambda x: f"{x} ({_dte(x)}d)",
                                   key="ot_exp")
            chain = data["chain"].get(expiry, {})
            df    = chain.get("calls" if opt_type=="Call" else "puts", pd.DataFrame())

            if not df.empty:
                strikes = sorted(df["strike"].dropna().unique().tolist())
                strike  = st.selectbox("Strike", strikes,
                                        format_func=lambda x: f"${x:,.2f}",
                                        key="ot_strike")

                # Show contract details
                row = df[df["strike"] == strike]
                if not row.empty:
                    r = row.iloc[0]
                    occ_symbol = str(r.get("option_symbol",""))
                    bid = r.get("bid"); ask = r.get("ask")
                    mid = round((bid+ask)/2, 2) if bid and ask else None
                    iv  = r.get("iv"); delta = r.get("delta")
                    theta = r.get("theta"); dte_val = r.get("dte")

                    ca, cb, cc = st.columns(3)
                    ca.metric("Bid", f"${bid:.2f}" if bid else "—")
                    cb.metric("Ask", f"${ask:.2f}" if ask else "—")
                    cc.metric("Mid", f"${mid:.2f}" if mid else "—")

                    cd, ce, cf = st.columns(3)
                    cd.metric("IV",    f"{iv*100:.1f}%"  if iv    else "—")
                    ce.metric("Delta", f"{delta:.3f}"    if delta  else "—")
                    cf.metric("Theta", f"{theta:.4f}"    if theta  else "—")

                    st.caption(f"Contract: `{occ_symbol}`  ·  DTE: {dte_val}")

                    # AI Trade Thesis
                    if st.button("🤖 AI Trade Thesis", key="ai_thesis_btn",
                                  use_container_width=True):
                        with st.spinner("Generating trade thesis…"):
                            thesis = generate_trade_thesis(
                                ticker=ticker,
                                option_type=opt_type.lower(),
                                strike=float(strike),
                                expiry=str(expiry),
                                dte=int(dte_val or 0),
                                iv=float(r.get("iv")) if r.get("iv") else None,
                                delta=float(r.get("delta")) if r.get("delta") else None,
                                theta=float(r.get("theta")) if r.get("theta") else None,
                                bid=float(bid) if bid else None,
                                ask=float(ask) if ask else None,
                            )
                        st.session_state["ai_thesis_text"] = thesis

                    if st.session_state.get("ai_thesis_text"):
                        st.info(st.session_state["ai_thesis_text"])
            else:
                strike = None; occ_symbol = ""; mid = None
                st.info("No contracts for this expiry.")
        else:
            expiry = None; strike = None; occ_symbol = ""; mid = None
            st.warning("Chain not loaded — click Refresh on the Chain Viewer tab.")

    with col2:
        st.markdown("#### Order Details")
        side = st.radio("Action", ["Buy to Open", "Sell to Open",
                                   "Buy to Close", "Sell to Close"],
                        key="ot_side")
        alpaca_side = "buy" if side.startswith("Buy") else "sell"

        qty = st.number_input("Contracts", min_value=1, max_value=100,
                               value=1, step=1, key="ot_qty",
                               help="1 contract = 100 shares")

        order_type = st.radio("Order Type", ["Limit", "Market"],
                               horizontal=True, key="ot_order_type")

        limit_price = None
        if order_type == "Limit":
            default_lp = mid or 1.0
            limit_price = st.number_input(
                "Limit Price (per share)",
                value=float(default_lp),
                min_value=0.01, step=0.01, format="%.2f",
                key="ot_limit"
            )
            if qty and limit_price:
                st.caption(
                    f"Total debit: **${limit_price * qty * 100:,.2f}** "
                    f"({qty} × {limit_price:.2f} × 100)"
                )

        tif = st.selectbox("Time in Force", ["day", "gtc"], key="ot_tif")

        # ── Submit ────────────────────────────────────────────
        st.markdown("---")
        col_sub, col_info = st.columns([1, 2])
        with col_sub:
            submit = st.button(
                f"{'📄' if paper else '⚡'} Submit Order",
                type="primary", key="ot_submit",
                use_container_width=True,
                disabled=not bool(occ_symbol),
            )
        with col_info:
            if occ_symbol:
                st.caption(f"{'Paper' if paper else '**LIVE**'} order for `{occ_symbol}`")
            else:
                st.caption("Select a contract to enable order submission.")

        if submit and occ_symbol:
            req = OptionsOrderRequest(
                option_symbol=occ_symbol,
                qty=int(qty),
                side=alpaca_side,
                order_type=order_type.lower(),
                tif=tif,
                limit_price=limit_price,
            )
            broker = AlpacaOptionsBroker(paper=paper)
            with st.spinner("Submitting order…"):
                resp = broker.submit_order(req)

            if resp.status == "error":
                st.error(f"❌ Order failed: {resp.error}")
            else:
                st.success(
                    f"✅ Order submitted — ID: `{resp.order_id}` "
                    f"Status: **{resp.status}**"
                )
                ensure_tables(db)
                save_order(db, tenant_id, user_id, req, resp)
                # Clear positions cache
                for k in list(st.session_state.keys()):
                    if "opt_pos" in k: del st.session_state[k]

    # ── Order History ─────────────────────────────────────────
    with st.expander("📋 Recent Orders", expanded=False):
        ensure_tables(db)
        history = get_order_history(db, tenant_id, limit=20)
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else:
            st.caption("No orders placed yet.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — POSITIONS
# ══════════════════════════════════════════════════════════════════════════════

def _render_positions(db, tenant_id: str, paper: bool):
    st.subheader("📈 Options Positions")
    st.caption("Live positions from Alpaca · P&L · Greeks exposure · DTE countdown")

    cache_key = "opt_positions"
    col_r, col_info = st.columns([1, 5])
    with col_r:
        if st.button("↺ Refresh", key="pos_refresh"):
            if cache_key in st.session_state: del st.session_state[cache_key]

    if cache_key not in st.session_state:
        with st.spinner("Loading positions…"):
            broker = AlpacaOptionsBroker(paper=paper)
            st.session_state[cache_key] = broker.list_options_positions()

    positions = st.session_state.get(cache_key, [])

    # Account summary
    acc_key = "opt_account"
    if acc_key not in st.session_state:
        broker = AlpacaOptionsBroker(paper=paper)
        st.session_state[acc_key] = broker.get_account()
    acc = st.session_state[acc_key]

    bp      = float(acc.get("buying_power") or acc.get("options_buying_power") or 0)
    eq      = float(acc.get("equity") or acc.get("portfolio_value") or 0)
    cash    = float(acc.get("cash") or 0)
    mode_str= "📄 Paper" if paper else "⚡ Live"

    c1,c2,c3,c4 = st.columns(4)
    c1.metric(f"Account ({mode_str})", f"${eq:,.2f}")
    c2.metric("Buying Power",          f"${bp:,.2f}")
    c3.metric("Cash",                  f"${cash:,.2f}")
    c4.metric("Options Positions",     len(positions))

    if not positions:
        st.info(
            "No open options positions in your Alpaca "
            f"{'paper' if paper else 'live'} account."
        )
        _render_order_history_compact(db, tenant_id)
        return

    # ── Positions table ───────────────────────────────────────
    rows = []
    total_value = 0; total_pnl = 0
    for p in positions:
        total_value += p.market_value
        total_pnl   += p.unrealized_pnl
        pnl_pct = p.unrealized_pnl / max(0.01, abs(p.avg_cost * p.qty * 100)) * 100
        rows.append({
            "Contract":   p.option_symbol,
            "Underlying": p.underlying,
            "Type":       p.option_type.upper() if p.option_type else "—",
            "Strike":     f"${p.strike:,.2f}" if p.strike else "—",
            "Expiry":     p.expiry,
            "DTE":        p.dte,
            "Qty":        int(p.qty),
            "Avg Cost":   f"${p.avg_cost:.2f}",
            "Mkt Value":  f"${p.market_value:,.2f}",
            "Unreal P&L": p.unrealized_pnl,
            "P&L %":      round(pnl_pct, 1),
        })

    c1,c2,c3 = st.columns(3)
    c1.metric("Total Options Value", f"${total_value:,.2f}")
    c2.metric("Unrealized P&L",      f"${total_pnl:,.2f}",
              delta_color="normal" if total_pnl >= 0 else "inverse")
    c3.metric("Avg P&L %",
              f"{(total_pnl/max(0.01,total_value)*100):+.1f}%")

    df = pd.DataFrame(rows)
    styled = df.style.map(
        lambda v: f"color: {CALL_CLR}" if isinstance(v,float) and v>0
                  else (f"color: {PUT_CLR}" if isinstance(v,float) and v<0 else ""),
        subset=["Unreal P&L","P&L %"]
    ).format({"Unreal P&L": "${:,.2f}", "P&L %": "{:+.1f}%"})
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ── DTE heatmap ───────────────────────────────────────────
    expiring_soon = [p for p in positions if 0 <= p.dte <= 7]
    if expiring_soon:
        names = ", ".join(f"`{p.option_symbol}`" for p in expiring_soon[:5])
        st.warning(f"⚠️ **{len(expiring_soon)} position(s) expiring within 7 days:** {names}")

    # ── AI Risk Scanner ───────────────────────────────────────
    st.divider()
    col_risk, _ = st.columns([1, 4])
    with col_risk:
        scan_btn = st.button("🤖 AI Risk Scan", key="ai_risk_scan",
                              type="primary", use_container_width=True)
    if scan_btn and positions:
        with st.spinner("Scanning portfolio risk…"):
            risk = scan_portfolio_risk(positions)
        st.session_state["ai_risk_result"] = risk

    risk = st.session_state.get("ai_risk_result")
    if risk:
        level = risk.get("risk_level","Unknown")
        level_colors = {
            "Low": "🟢", "Medium": "🟡",
            "High": "🔴", "Critical": "🚨"
        }
        icon = level_colors.get(level, "⚪")
        st.markdown(f"### {icon} Portfolio Risk: **{level}**")
        st.info(risk.get("summary",""))
        flags = risk.get("flags", [])
        if flags:
            st.markdown("**Risk Flags:**")
            for flag in flags:
                st.markdown(f"- ⚠️ {flag}")
        urgent = risk.get("urgent_action")
        if urgent:
            st.warning(f"**Urgent Action:** {urgent}")
    elif not positions:
        pass
    else:
        st.caption("Click 'AI Risk Scan' to analyze your portfolio risk.")

    _render_order_history_compact(db, tenant_id)


def _render_order_history_compact(db, tenant_id: str):
    with st.expander("📋 Order History", expanded=False):
        history = get_order_history(db, tenant_id, 20)
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else:
            st.caption("No order history.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — STRATEGY BUILDER
# ══════════════════════════════════════════════════════════════════════════════

STRATEGIES = {
    "Long Call":         [("buy","call",1)],
    "Long Put":          [("buy","put",1)],
    "Covered Call":      [("buy","stock",100), ("sell","call",1)],
    "Protective Put":    [("buy","stock",100), ("buy","put",1)],
    "Bull Call Spread":  [("buy","call",1), ("sell","call",1)],
    "Bear Put Spread":   [("buy","put",1),  ("sell","put",1)],
    "Long Straddle":     [("buy","call",1), ("buy","put",1)],
    "Long Strangle":     [("buy","call",1), ("buy","put",1)],
    "Iron Condor":       [("buy","put",1),  ("sell","put",1),
                          ("sell","call",1),("buy","call",1)],
    "Butterfly Spread":  [("buy","call",1), ("sell","call",2), ("buy","call",1)],
}

def _render_strategy_builder(ticker: str):
    st.subheader(f"🏗 Strategy Builder — {ticker}")
    st.caption("Multi-leg strategy payoff diagrams · Greeks summary")

    col_strat, col_price, col_ai = st.columns([2, 2, 1])
    with col_strat:
        strategy = st.selectbox("Strategy", list(STRATEGIES.keys()),
                                 key="sb_strategy")
    with col_price:
        current_price = st.number_input("Current Stock Price ($)",
                                         value=100.0, min_value=0.01, step=0.01,
                                         key="sb_price")
    with col_ai:
        st.write("")
        ai_rec_btn = st.button("🤖 AI Pick", key="sb_ai_rec",
                                use_container_width=True,
                                help="Let AI recommend the best strategy")

    # AI Strategy Recommender
    if ai_rec_btn or st.session_state.get("sb_show_recommender"):
        st.session_state["sb_show_recommender"] = True
        with st.expander("🤖 AI Strategy Recommendation", expanded=True):
            c_view, c_conv, c_risk = st.columns(3)
            with c_view:
                ai_view = st.radio("Market View", ["bullish","bearish","neutral"],
                                    horizontal=True, key="ai_view")
            with c_conv:
                ai_conv = st.radio("Conviction", ["high","medium","low"],
                                    horizontal=True, key="ai_conv")
            with c_risk:
                ai_risk = st.radio("Risk Tolerance", ["aggressive","moderate","conservative"],
                                    horizontal=True, key="ai_risk")

            if st.button("Get Recommendation", key="ai_get_rec", type="primary"):
                with st.spinner("Analyzing market conditions…"):
                    rec = recommend_strategy(
                        ticker=ticker,
                        current_price=float(current_price),
                        market_view=ai_view,
                        conviction=ai_conv,
                        risk_tolerance=ai_risk,
                    )
                st.session_state["ai_strategy_rec"] = rec

            rec = st.session_state.get("ai_strategy_rec")
            if rec:
                rec_name = rec.get("strategy","—")
                st.success(f"**Recommended: {rec_name}**")
                c1, c2 = st.columns(2)
                c1.markdown(f"**Rationale:** {rec.get('rationale','—')}")
                c2.markdown(f"**Strike guidance:** {rec.get('strike_guidance','—')}")
                c1.markdown(f"**Ideal DTE:** {rec.get('ideal_dte','—')} days")
                c2.markdown(f"**Max risk:** {rec.get('max_risk','—')}")
                c1.markdown(f"**IV note:** {rec.get('iv_note','—')}")
                c2.markdown(f"**Ideal conditions:** {rec.get('ideal_conditions','—')}")
                if st.button(f"Apply: {rec_name}", key="apply_rec"):
                    if rec_name in STRATEGIES:
                        st.session_state["sb_strategy"] = rec_name
                        st.rerun()

    # ── Leg configuration ─────────────────────────────────────
    st.markdown("#### Legs")
    legs_template = STRATEGIES[strategy]
    legs = []

    cols_per_leg = 4
    for i, (side_def, type_def, qty_def) in enumerate(legs_template):
        is_stock = type_def == "stock"
        with st.container():
            c1,c2,c3,c4,c5 = st.columns([1,1,1,1,2])
            c1.markdown(f"**Leg {i+1}**")
            side = c2.selectbox(
                "Side",
                ["buy", "sell"],
                index=0 if side_def == "buy" else 1,
                key=f"sb_side_{i}",
                label_visibility="collapsed"
            )
            if not is_stock:
                opt_type = c3.selectbox(
                    "Option Type",
                    ["call", "put"],
                    index=0 if type_def == "call" else 1,
                    key=f"sb_type_{i}",
                    label_visibility="collapsed"
                )

                strike = c4.number_input(
                    "Strike",
                    value=float(round(current_price * (1.02 if i % 2 == 0 else 0.98), 2)),
                    min_value=0.01,
                    step=1.0,
                    key=f"sb_strike_{i}",
                    label_visibility="collapsed"
                )

                premium = c5.number_input(
                    "Premium ($)",
                    value=2.0,
                    min_value=0.0,
                    step=0.1,
                    key=f"sb_prem_{i}"
                )

                legs.append({
                    "side": side,
                    "type": opt_type,
                    "strike": strike,
                    "premium": premium,
                    "qty": 100,
                })

            else:
                c3.markdown("Stock")

                strike = c4.number_input(
                    "Stock Strike",
                    value=float(current_price),
                    min_value=0.01,
                    step=1.0,
                    key=f"sb_strike_{i}",
                    label_visibility="collapsed"
                )

                legs.append({
                    "side": side,
                    "type": "stock",
                    "strike": float(strike),
                    "premium": float(current_price),
                    "qty": 1,
                })

            # ── Payoff calculation ────────────────────────────────────
            price_range = np.linspace(current_price * 0.6, current_price * 1.4, 300)
            payoff = np.zeros(len(price_range))

    for leg in legs:
        mult = 1 if leg["side"] == "buy" else -1
        qty  = leg["qty"]
        if leg["type"] == "call":
            profit = mult * (np.maximum(price_range - leg["strike"], 0) - leg["premium"]) * qty
        elif leg["type"] == "put":
            profit = mult * (np.maximum(leg["strike"] - price_range, 0) - leg["premium"]) * qty
        else:  # stock
            profit = mult * (price_range - leg["premium"]) * qty
        payoff += profit

    # ── Greeks summary ────────────────────────────────────────
    total_delta = sum(
        (1 if l["side"]=="buy" else -1) * (1 if l["type"]=="call" else -1 if l["type"]=="put" else 0)
        * l["qty"] / 100
        for l in legs if l["type"] != "stock"
    )
    max_profit = float(np.max(payoff))
    max_loss   = float(np.min(payoff))
    breakevens = []
    for j in range(len(payoff)-1):
        if (payoff[j] < 0) != (payoff[j+1] < 0):
            be = price_range[j] + (0 - payoff[j]) * (price_range[j+1]-price_range[j]) / (payoff[j+1]-payoff[j]+1e-9)
            breakevens.append(round(float(be), 2))

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Max Profit", f"${max_profit:,.2f}" if max_profit < 1e6 else "Unlimited")
    c2.metric("Max Loss",   f"${max_loss:,.2f}"   if max_loss  > -1e6 else "Unlimited")
    c3.metric("Breakeven(s)", ", ".join(f"${b}" for b in breakevens[:2]) or "—")
    c4.metric("Net Delta",  f"{total_delta:+.2f}")

    # ── Payoff chart ──────────────────────────────────────────
    if not PLOTLY:
        st.info("Install plotly for payoff chart.")
        return

    fig = go.Figure()
    pos_mask = payoff >= 0
    neg_mask = payoff <  0

    # Profit zone (green fill)
    fig.add_trace(go.Scatter(
        x=price_range, y=np.where(pos_mask, payoff, 0),
        fill="tozeroy", fillcolor="rgba(29,158,117,0.15)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, name="Profit",
    ))
    # Loss zone (red fill)
    fig.add_trace(go.Scatter(
        x=price_range, y=np.where(neg_mask, payoff, 0),
        fill="tozeroy", fillcolor="rgba(226,75,74,0.15)",
        line=dict(color="rgba(0,0,0,0)"), showlegend=False, name="Loss",
    ))
    # P&L line
    fig.add_trace(go.Scatter(
        x=price_range, y=payoff,
        line=dict(color="#378ADD", width=2.5),
        name="P&L at Expiry",
    ))
    # Zero line
    fig.add_hline(y=0, line_dash="dot", line_color="#4A5568")
    # Current price
    fig.add_vline(x=current_price, line_dash="dash", line_color="#FFC107",
                  annotation_text=f"Current ${current_price:.2f}",
                  annotation_position="top right")
    # Breakevens
    for be in breakevens:
        fig.add_vline(x=be, line_dash="dot", line_color="#8B949E",
                      annotation_text=f"BE ${be}",
                      annotation_position="bottom right")
    # Strike markers
    for leg in legs:
        if leg["type"] != "stock":
            clr = CALL_CLR if leg["type"]=="call" else PUT_CLR
            fig.add_vline(x=leg["strike"], line_dash="dot", line_color=clr,
                          annotation_text=f"{'Buy' if leg['side']=='buy' else 'Sell'} {leg['type'].title()} ${leg['strike']:.0f}",
                          annotation_font_size=10)

    fig.update_layout(
        title=f"{strategy} — P&L at Expiry",
        xaxis_title="Stock Price at Expiry ($)",
        yaxis_title="Profit / Loss ($)",
        template="plotly_dark",
        paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
        height=420, margin=dict(l=0,r=20,t=40,b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.05),
    )
    fig.update_xaxes(gridcolor="#21262D")
    fig.update_yaxes(gridcolor="#21262D", zeroline=True, zerolinecolor="#30363D")
    st.plotly_chart(fig, use_container_width=True)

    # ── Strategy description ──────────────────────────────────
    descriptions = {
        "Long Call":        "Bullish. Profits if stock rises above strike + premium. Max loss = premium paid.",
        "Long Put":         "Bearish. Profits if stock falls below strike - premium. Max loss = premium paid.",
        "Covered Call":     "Neutral/Bullish. Own stock, sell upside. Income strategy, limits upside.",
        "Protective Put":   "Insurance on long stock. Limits downside at cost of premium.",
        "Bull Call Spread":  "Bullish limited risk. Buy lower strike call, sell higher strike call. Lower cost than naked call.",
        "Bear Put Spread":   "Bearish limited risk. Buy higher strike put, sell lower strike put.",
        "Long Straddle":    "Volatility play. Profits from large move in either direction. Requires big move to be profitable.",
        "Long Strangle":    "Cheaper volatility play than straddle. Requires even larger move to profit.",
        "Iron Condor":      "Neutral. Sells both a call spread and put spread. Profits if stock stays in range.",
        "Butterfly Spread": "Neutral. Profits maximised if stock expires exactly at middle strike.",
    }
    if strategy in descriptions:
        st.info(f"**{strategy}:** {descriptions[strategy]}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — P&L CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

def _bs_price(S, K, T, r, sigma, opt_type):
    """Black-Scholes option price."""
    if T <= 0 or sigma <= 0: return max(0, S-K) if opt_type=="call" else max(0, K-S)
    d1 = (math.log(S/K) + (r + sigma**2/2)*T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    from scipy.stats import norm
    if opt_type == "call":
        return S * norm.cdf(d1) - K * math.exp(-r*T) * norm.cdf(d2)
    else:
        return K * math.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)

def _bs_greeks(S, K, T, r, sigma, opt_type):
    try:
        from scipy.stats import norm
        if T <= 0 or sigma <= 0:
            return {"delta": 1.0 if opt_type=="call" else -1.0,
                    "gamma":0,"theta":0,"vega":0}
        d1 = (math.log(S/K) + (r + sigma**2/2)*T) / (sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        delta = norm.cdf(d1) if opt_type=="call" else norm.cdf(d1)-1
        gamma = norm.pdf(d1) / (S*sigma*math.sqrt(T))
        theta = (-(S*norm.pdf(d1)*sigma)/(2*math.sqrt(T))
                 - r*K*math.exp(-r*T)*norm.cdf(d2 if opt_type=="call" else -d2)) / 365
        vega  = S*norm.pdf(d1)*math.sqrt(T)/100
        return {"delta":round(delta,4),"gamma":round(gamma,6),
                "theta":round(theta,4),"vega":round(vega,4)}
    except: return {"delta":None,"gamma":None,"theta":None,"vega":None}

def _render_pnl_calculator(ticker: str):
    st.subheader(f"💰 Options P&L Calculator — {ticker}")
    st.caption("Black-Scholes pricing · Interactive payoff · Greeks at any price/date")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Option Parameters")
        current_price = st.number_input("Current Stock Price ($)", value=100.0,
                                         min_value=0.01, step=0.01, key="calc_S")
        strike   = st.number_input("Strike Price ($)", value=100.0,
                                    min_value=0.01, step=0.01, key="calc_K")
        opt_type = st.radio("Option Type", ["call","put"], horizontal=True,
                             key="calc_type")
        dte_days = st.slider("Days to Expiry", 1, 365, 30, key="calc_dte")
        iv       = st.slider("Implied Volatility (%)", 5, 200, 25, key="calc_iv") / 100
        r        = st.slider("Risk-Free Rate (%)", 0, 10, 5, key="calc_r") / 100
        contracts= st.number_input("Contracts (×100)", value=1, min_value=1,
                                    max_value=100, step=1, key="calc_qty")
        side     = st.radio("Position", ["Long (Buy)","Short (Sell)"],
                             horizontal=True, key="calc_side")

    T = dte_days / 365
    try:
        price_now = _bs_price(current_price, strike, T, r, iv, opt_type)
    except Exception:
        price_now = 0

    with col2:
        st.markdown("#### Current Valuation")
        greeks = _bs_greeks(current_price, strike, T, r, iv, opt_type)
        ca,cb = st.columns(2)
        ca.metric("Option Price",   f"${price_now:.2f}")
        cb.metric("Total Value",    f"${price_now*contracts*100:,.2f}")
        ca.metric("Δ Delta",        f"{greeks['delta']:.4f}" if greeks['delta'] is not None else "—")
        cb.metric("Γ Gamma",        f"{greeks['gamma']:.6f}" if greeks['gamma'] is not None else "—")
        ca.metric("Θ Theta/day",    f"${greeks['theta']:.4f}" if greeks['theta'] is not None else "—")
        cb.metric("V Vega/1%IV",    f"${greeks['vega']:.4f}"  if greeks['vega']  is not None else "—")

        # Cost basis for P&L
        paid = st.number_input("Premium Paid/Received ($)",
                                value=float(round(price_now, 2)),
                                min_value=0.0, step=0.01, format="%.2f",
                                key="calc_paid",
                                help="The actual price you bought/sold the option for")

    if not PLOTLY:
        st.info("Install plotly for P&L chart.")
        return

    # ── P&L across stock prices ───────────────────────────────
    price_range = np.linspace(current_price * 0.5, current_price * 1.5, 300)
    mult = 1 if side == "Long (Buy)" else -1

    # At expiry
    if opt_type == "call":
        pnl_expiry = mult * (np.maximum(price_range - strike, 0) - paid) * contracts * 100
    else:
        pnl_expiry = mult * (np.maximum(strike - price_range, 0) - paid) * contracts * 100

    # At various DTEs (for theta decay)
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=["P&L at Expiry", "P&L vs Stock Price (today)"])

    # Left: expiry payoff
    fig.add_trace(go.Scatter(
        x=price_range, y=pnl_expiry,
        line=dict(color="#378ADD", width=2.5),
        name="At Expiry", fill="tozeroy",
        fillcolor="rgba(55,138,221,0.1)",
    ), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color="#4A5568", row=1, col=1)
    fig.add_vline(x=current_price, line_dash="dash", line_color="#FFC107",
                  row=1, col=1)

    # Right: current value P&L across prices
    try:
        pnl_today = []
        for sp in price_range:
            try:
                val = _bs_price(sp, strike, T, r, iv, opt_type)
                pnl_today.append(mult * (val - paid) * contracts * 100)
            except: pnl_today.append(0)
        fig.add_trace(go.Scatter(
            x=price_range, y=pnl_today,
            line=dict(color=CALL_CLR if opt_type=="call" else PUT_CLR, width=2),
            name=f"Today (DTE={dte_days})",
        ), row=1, col=2)
        fig.add_hline(y=0, line_dash="dot", line_color="#4A5568", row=1, col=2)
        fig.add_vline(x=current_price, line_dash="dash", line_color="#FFC107",
                      row=1, col=2)
    except Exception: pass

    fig.update_layout(
        template="plotly_dark", paper_bgcolor="#0F1117", plot_bgcolor="#161B22",
        height=380, margin=dict(l=0,r=20,t=40,b=20), hovermode="x",
        legend=dict(orientation="h",y=1.05),
    )
    fig.update_xaxes(title_text="Stock Price ($)", gridcolor="#21262D")
    fig.update_yaxes(title_text="P&L ($)", gridcolor="#21262D",
                     zeroline=True, zerolinecolor="#30363D")
    st.plotly_chart(fig, use_container_width=True)

    # ── Scenario table ────────────────────────────────────────
    st.markdown("#### Scenario Analysis")
    scenarios = []
    for move_pct in [-30,-20,-15,-10,-5,0,5,10,15,20,30]:
        sp  = current_price * (1 + move_pct/100)
        if opt_type == "call":
            pnl_exp = mult * (max(sp-strike,0) - paid) * contracts * 100
        else:
            pnl_exp = mult * (max(strike-sp,0) - paid) * contracts * 100
        try:
            val_now = _bs_price(sp, strike, T, r, iv, opt_type)
            pnl_now = mult * (val_now - paid) * contracts * 100
        except: pnl_now = 0
        scenarios.append({
            "Stock Move": f"{move_pct:+d}%",
            "Stock Price": f"${sp:.2f}",
            "P&L Today":  pnl_now,
            "P&L Expiry": pnl_exp,
        })

    sc_df = pd.DataFrame(scenarios)
    def _color(v):
        try:
            return (f"color: {CALL_CLR}; font-weight:bold" if float(str(v).replace("$","").replace(",","")) > 0
                    else f"color: {PUT_CLR}; font-weight:bold" if float(str(v).replace("$","").replace(",","")) < 0
                    else "")
        except: return ""

    styled = sc_df.style.map(_color, subset=["P&L Today","P&L Expiry"])
    styled = styled.format({"P&L Today": "${:,.2f}", "P&L Expiry": "${:,.2f}"})
    st.dataframe(styled, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — AI ANALYSIS (Q&A + Flow Alerts)
# ══════════════════════════════════════════════════════════════════════════════

def _render_ai_analysis(ticker: str, paper: bool):
    st.subheader(f"🤖 AI Options Analysis — {ticker}")
    st.caption("Chain Q&A · Unusual flow interpretation · AI-powered options intelligence")

    # Load chain for context
    chain_key = f"opt_chain_{ticker}"
    if chain_key not in st.session_state:
        with st.spinner("Loading chain…"):
            st.session_state[chain_key] = get_options_chain(ticker)
    chain_data = st.session_state.get(chain_key, {})

    tab_qa, tab_flow = st.tabs(["💬 Chain Q&A", "🌊 Flow Alerts"])

    with tab_qa:
        _render_qa_assistant(ticker, chain_data)

    with tab_flow:
        _render_flow_alerts(ticker, chain_data)


def _render_qa_assistant(ticker: str, chain_data: dict):
    st.markdown("#### 💬 Options Chain Q&A")
    st.caption(
        "Ask anything about the options chain — IV skew, max pain, "
        "unusual activity, strategy ideas, Greeks interpretation."
    )

    # Build chain summary for context
    chain_summary = build_chain_summary(ticker, chain_data)

    # Show context being used
    with st.expander("📋 Chain context loaded into AI", expanded=False):
        st.code(chain_summary)

    # Conversation history
    hist_key = f"qa_history_{ticker}"
    if hist_key not in st.session_state:
        st.session_state[hist_key] = []

    history = st.session_state[hist_key]

    # Suggested questions
    suggested = [
        f"What does the put/call ratio tell me about sentiment on {ticker}?",
        "Where is the max pain strike and why does it matter?",
        "Is the IV skew showing fear in puts or calls?",
        "What's the best strategy given the current IV environment?",
        "Which expiry has the most unusual activity?",
    ]

    if not history:
        st.markdown("**Suggested questions:**")
        for q in suggested:
            if st.button(q, key=f"sq_{q[:20]}", use_container_width=True):
                st.session_state[f"qa_prefill_{ticker}"] = q

    # Display conversation
    for msg in history:
        role = msg["role"]
        with st.chat_message(role):
            st.markdown(msg["content"])

    # Input
    prefill = st.session_state.pop(f"qa_prefill_{ticker}", "")
    question = st.chat_input(
        f"Ask about {ticker} options…",
        key=f"qa_input_{ticker}",
    )
    if prefill and not question:
        question = prefill

    if question:
        # Show user message
        with st.chat_message("user"):
            st.markdown(question)
        history.append({"role": "user", "content": question})

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Analyzing…"):
                answer = options_qa(
                    question=question,
                    ticker=ticker,
                    chain_summary=chain_summary,
                    conversation_history=history[:-1],
                )
            st.markdown(answer)
        history.append({"role": "assistant", "content": answer})
        st.session_state[hist_key] = history

    if history:
        if st.button("🗑 Clear conversation", key=f"qa_clear_{ticker}"):
            st.session_state[hist_key] = []
            st.rerun()


def _render_flow_alerts(ticker: str, chain_data: dict):
    st.markdown("#### 🌊 Unusual Flow Interpretation")
    st.caption(
        "AI interpretation of unusual options activity — "
        "volume spikes, OI build-up, dark pool context."
    )

    col_thresh, col_scan = st.columns([2, 1])
    with col_thresh:
        threshold = st.slider(
            "Vol/OI ratio threshold (flag when volume > X × open interest)",
            min_value=1.0, max_value=10.0, value=2.0, step=0.5,
            key="flow_threshold",
        )
    with col_scan:
        st.write("")
        scan = st.button("🔍 Scan for Unusual Flow",
                          key="flow_scan", type="primary",
                          use_container_width=True)

    if scan or st.session_state.get("flow_results"):
        if scan:
            with st.spinner("Detecting unusual activity…"):
                unusual = detect_unusual_contracts(chain_data, threshold)
                st.session_state["flow_unusual"] = unusual

                # Get dark pool data
                dp_data = {}
                try:
                    from modules.options_flow.flow_service import get_finra_dark_pool
                    dp_data = get_finra_dark_pool(ticker)
                except Exception:
                    pass

                # PCR
                all_rows = chain_data.get("all_rows")
                pcr = 1.0
                if all_rows is not None and not all_rows.empty:
                    call_vol = all_rows[all_rows["type"]=="call"]["volume"].fillna(0).sum()
                    put_vol  = all_rows[all_rows["type"]=="put"]["volume"].fillna(0).sum()
                    pcr = round(put_vol / max(1, call_vol), 2)

                if unusual:
                    with st.spinner("AI interpreting flow signals…"):
                        alerts = interpret_flow_alerts(
                            ticker=ticker,
                            unusual_contracts=[{
                                "type":         r.get("type",""),
                                "strike":       r.get("strike",0),
                                "expiry":       r.get("expiry",""),
                                "volume":       int(r.get("volume",0) or 0),
                                "open_interest":int(r.get("open_interest",0) or 0),
                                "iv":           r.get("iv"),
                                "vol_oi_ratio": round(float(r.get("vol_oi_ratio",0)),1),
                            } for r in unusual],
                            dark_pool_data=dp_data,
                            pcr=pcr,
                        )
                    st.session_state["flow_results"] = alerts
                else:
                    st.session_state["flow_results"] = []
                    st.info(f"No contracts with Vol/OI ratio ≥ {threshold:.1f}× found.")

        unusual = st.session_state.get("flow_unusual", [])
        alerts  = st.session_state.get("flow_results", [])

        if unusual:
            st.markdown(f"**Found {len(unusual)} unusual contracts** (Vol/OI ≥ {threshold:.1f}×):")

            # Raw unusual table
            import pandas as pd
            df = pd.DataFrame(unusual)
            fmt_cols = [c for c in ["type","strike","expiry","volume",
                                     "open_interest","iv","vol_oi_ratio"]
                        if c in df.columns]
            if "iv" in df.columns:
                df["iv"] = df["iv"].apply(
                    lambda x: f"{float(x)*100:.0f}%" if x is not None else "—"
                )
            if "vol_oi_ratio" in df.columns:
                df["vol_oi_ratio"] = df["vol_oi_ratio"].apply(
                    lambda x: f"{float(x):.1f}×" if x is not None else "—"
                )
            st.dataframe(df[fmt_cols].rename(columns={
                "type":"Type","strike":"Strike","expiry":"Expiry",
                "volume":"Volume","open_interest":"OI",
                "iv":"IV","vol_oi_ratio":"Vol/OI"
            }), use_container_width=True, hide_index=True)

        if alerts:
            st.markdown("**🤖 AI Interpretations:**")
            sentiment_icons = {
                "bullish": "🟢",
                "bearish": "🔴",
                "neutral": "⚪",
                "hedging": "🛡️",
            }
            for alert in alerts:
                icon = sentiment_icons.get(alert.get("sentiment","neutral"), "⚪")
                st.markdown(
                    f"{icon} **{alert.get('contract','—')}** — "
                    f"{alert.get('interpretation','')}"
                )


# ── Helpers ────────────────────────────────────────────────────────────────────
def _dte(expiry_str: str) -> int:
    try:
        from datetime import date
        exp = datetime.strptime(expiry_str[:10], "%Y-%m-%d").date()
        return (exp - date.today()).days
    except: return 0