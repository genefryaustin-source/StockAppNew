"""
modules/options/options_strategy_command_center.py

Phase 5 — Multi-Leg Strategy Command Center UI.
Turns Smart Money, Dealer Analytics, Volatility, and AI context into scored
multi-leg strategy recommendations.
"""
from __future__ import annotations

from typing import Any
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
    PLOTLY = True
except Exception:
    PLOTLY = False

from modules.options.options_data_service import get_options_chain
from modules.options.options_strategy_recommender import generate_strategy_candidates, candidates_to_frame, filter_candidates
from modules.options.options_strategy_optimizer import optimize_strategy_candidates, scenario_objectives
from modules.options.options_strategy_backtester import backtest_strategy_proxy, backtest_to_frame
from modules.options.options_strategy_ai import explain_strategy_recommendation, summarize_strategy_command_center


def _load_chain(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    key = f"phase5_strategy_chain_{ticker.upper()}"
    if force_refresh or key not in st.session_state:
        with st.spinner(f"Loading options chain for {ticker}..."):
            st.session_state[key] = get_options_chain(ticker)
    return st.session_state.get(key, {})


def _load_candidates(ticker: str, force_refresh: bool = False) -> list[dict[str, Any]]:
    key = f"phase5_strategy_candidates_{ticker.upper()}"
    if force_refresh or key not in st.session_state:
        chain = _load_chain(ticker, force_refresh=force_refresh)
        with st.spinner("Building and scoring strategy candidates..."):
            st.session_state[key] = generate_strategy_candidates(ticker, chain, include_context=True)
    return list(st.session_state.get(key, []) or [])


def _candidate_selector(candidates: list[dict[str, Any]], key: str = "phase5_candidate") -> dict[str, Any] | None:
    if not candidates:
        return None
    names = [f"{c.get('strategy_name')} — {c.get('grade')} — {c.get('overall_score')}" for c in candidates]
    idx = st.selectbox("Strategy", list(range(len(names))), format_func=lambda i: names[i], key=key)
    return candidates[int(idx)]


def _render_candidate_metrics(candidate: dict[str, Any]):
    score = candidate.get("score") or {}
    metrics = candidate.get("metrics") or {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Overall", f"{candidate.get('overall_score', 0):.1f}", candidate.get("grade"))
    c2.metric("POP Score", f"{score.get('probability_score', 0):.1f}")
    c3.metric("Risk/Reward", f"{score.get('risk_reward_score', 0):.1f}")
    c4.metric("Smart Money", f"{score.get('smart_money_alignment_score', 0):.1f}")
    c5.metric("Dealer", f"{score.get('dealer_alignment_score', 0):.1f}")

    c6, c7, c8, c9 = st.columns(4)
    c6.metric("Max Profit", f"${float(metrics.get('max_profit') or 0):,.0f}")
    c7.metric("Max Loss", f"${float(metrics.get('max_loss') or 0):,.0f}")
    c8.metric("Expected Value", f"${float(metrics.get('expected_value') or 0):,.0f}")
    c9.metric("Capital", f"${float(metrics.get('capital_required') or 0):,.0f}")


def _render_legs(candidate: dict[str, Any]):
    legs = candidate.get("legs") or []
    if legs:
        st.dataframe(pd.DataFrame(legs), use_container_width=True, hide_index=True)
    else:
        st.info("This strategy is represented as a scoring template. Build exact legs in the Custom Builder or Strategy tab.")


def _render_top_table(candidates: list[dict[str, Any]]):
    df = candidates_to_frame(candidates)
    if df.empty:
        st.info("No strategy candidates available.")
        return
    st.dataframe(df, use_container_width=True, hide_index=True)


def _render_best_strategies(candidates: list[dict[str, Any]], ticker: str):
    st.markdown("#### Best Strategy Recommendations")
    _render_top_table(candidates[:15])
    selected = _candidate_selector(candidates, "phase5_best_selector")
    if selected:
        st.markdown("#### Selected Strategy")
        _render_candidate_metrics(selected)
        with st.expander("Legs / Structure", expanded=True):
            _render_legs(selected)
        with st.expander("Scoring Notes", expanded=False):
            for note in (selected.get("score") or {}).get("notes", []):
                st.markdown(f"- {note}")
        if st.button("🤖 Explain Selected Strategy", key=f"phase5_ai_explain_{ticker}", type="primary"):
            st.info(explain_strategy_recommendation(ticker, selected))


def _render_category(candidates: list[dict[str, Any]], category: str, ticker: str):
    rows = filter_candidates(candidates, category=category)
    st.markdown(f"#### {category} Strategy Candidates")
    _render_top_table(rows[:20])
    selected = _candidate_selector(rows, f"phase5_{category}_selector") if rows else None
    if selected:
        _render_candidate_metrics(selected)
        _render_legs(selected)


def _render_optimizer(candidates: list[dict[str, Any]], ticker: str):
    st.markdown("#### Strategy Optimizer")
    objective = st.selectbox("Optimization Objective", scenario_objectives(), key="phase5_objective")
    result = optimize_strategy_candidates(candidates, objective)
    if result.get("error"):
        st.warning(result["error"])
        return
    best = result["best_strategy"]
    st.success(f"Best match: {best.get('strategy_name')} — {best.get('grade')} — {best.get('overall_score')}")
    _render_candidate_metrics(best)
    _render_legs(best)
    st.markdown("#### Top 5 for Objective")
    _render_top_table(result.get("top_5", []))


def _render_backtester(candidates: list[dict[str, Any]], ticker: str):
    st.markdown("#### Strategy Backtesting Lab")
    selected = _candidate_selector(candidates, "phase5_backtest_selector")
    periods = st.slider("Proxy Backtest Trades", 25, 300, 120, 5, key="phase5_backtest_periods")
    if selected and st.button("Run Proxy Backtest", key=f"phase5_run_backtest_{ticker}", type="primary"):
        result = backtest_strategy_proxy(selected, periods=periods)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Win Rate", f"{result['win_rate']:.1%}")
        c2.metric("Total P&L", f"${result['total_pnl']:,.0f}")
        c3.metric("Expectancy", f"${result['expectancy']:,.0f}")
        c4.metric("Max Drawdown", f"${result['max_drawdown']:,.0f}")
        df = backtest_to_frame(result)
        if not df.empty:
            if PLOTLY:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df["Trade"], y=df["Cumulative P&L"], mode="lines", name="Cumulative P&L"))
                fig.update_layout(height=360, title=f"{selected.get('strategy_name')} Proxy Backtest", xaxis_title="Trade", yaxis_title="Cumulative P&L")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.line_chart(df.set_index("Trade")[["Cumulative P&L"]])
            st.dataframe(df, use_container_width=True, hide_index=True)


def _render_custom_builder(ticker: str):
    st.markdown("#### Custom Multi-Leg Builder")
    if "phase5_custom_legs" not in st.session_state:
        st.session_state["phase5_custom_legs"] = []

    with st.form("phase5_custom_leg_form"):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        side = c1.selectbox("Side", ["buy", "sell"], key="phase5_custom_side")
        opt_type = c2.selectbox("Type", ["call", "put", "stock"], key="phase5_custom_type")
        expiry = c3.text_input("Expiry", "30D", key="phase5_custom_expiry")
        strike = c4.number_input("Strike", 0.0, 100000.0, 100.0, 1.0, key="phase5_custom_strike")
        premium = c5.number_input("Premium", 0.0, 10000.0, 1.0, 0.05, key="phase5_custom_premium")
        qty = c6.number_input("Qty", 1, 100, 1, 1, key="phase5_custom_qty")
        submitted = st.form_submit_button("Add Leg")
        if submitted:
            st.session_state["phase5_custom_legs"].append({
                "side": side,
                "type": opt_type,
                "expiry": expiry,
                "strike": strike,
                "premium": premium,
                "qty": qty,
                "option_symbol": f"{ticker} {expiry} {opt_type.upper()} {strike}",
            })
    legs = st.session_state["phase5_custom_legs"]
    if legs:
        st.dataframe(pd.DataFrame(legs), use_container_width=True, hide_index=True)
        if st.button("Clear Custom Legs", key="phase5_clear_custom"):
            st.session_state["phase5_custom_legs"] = []
            st.rerun()
    else:
        st.info("Add legs to construct a custom strategy.")


def _render_ai_lab(candidates: list[dict[str, Any]], ticker: str):
    st.markdown("#### AI Strategy Lab")
    if st.button("Generate Strategy Desk Summary", key=f"phase5_summary_{ticker}", type="primary"):
        st.info(summarize_strategy_command_center(ticker, candidates))
    selected = _candidate_selector(candidates, "phase5_ai_lab_selector")
    if selected and st.button("Generate Institutional Recommendation", key=f"phase5_ai_selected_{ticker}"):
        st.info(explain_strategy_recommendation(ticker, selected))


def render_options_strategy_command_center(ticker: str):
    """Render Phase 5 Strategy Command Center."""
    st.subheader(f"🧠 Strategy Command Center — {ticker.upper()}")
    st.caption("Best strategies · scored multi-leg recommendations · optimizer · backtesting lab · AI strategy desk")

    c_refresh, c_filter1, c_filter2 = st.columns([1, 2, 2])
    with c_refresh:
        refresh = st.button("↺ Refresh", key=f"phase5_strategy_refresh_{ticker}", use_container_width=True)
    with c_filter1:
        min_score = st.slider("Minimum Score", 0, 100, 0, key="phase5_min_score")
    with c_filter2:
        category_filter = st.selectbox("Category", ["All", "Bullish", "Bearish", "Neutral", "Volatility", "Income", "Custom"], key="phase5_category_filter")

    candidates = _load_candidates(ticker, force_refresh=refresh)
    candidates = filter_candidates(candidates, category=category_filter, min_score=float(min_score)) if candidates else []

    if not candidates:
        st.warning("No candidates available. Verify options chain data is available for this ticker.")
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Candidates", len(candidates))
    k2.metric("Best Score", f"{float(candidates[0].get('overall_score') or 0):.1f}")
    k3.metric("Best Grade", str(candidates[0].get("grade") or "—"))
    k4.metric("Top Strategy", str(candidates[0].get("strategy_name") or "—"))

    tabs = st.tabs([
        "🎯 Best Strategies",
        "📈 Bullish",
        "📉 Bearish",
        "↔ Neutral",
        "⚡ Volatility",
        "🛡 Income",
        "🔬 Builder",
        "🧪 Backtest",
        "🤖 AI Lab",
    ])

    with tabs[0]:
        _render_best_strategies(candidates, ticker)
        st.divider()
        _render_optimizer(candidates, ticker)
    with tabs[1]:
        _render_category(candidates, "Bullish", ticker)
    with tabs[2]:
        _render_category(candidates, "Bearish", ticker)
    with tabs[3]:
        _render_category(candidates, "Neutral", ticker)
    with tabs[4]:
        _render_category(candidates, "Volatility", ticker)
    with tabs[5]:
        _render_category(candidates, "Income", ticker)
    with tabs[6]:
        _render_custom_builder(ticker)
    with tabs[7]:
        _render_backtester(candidates, ticker)
    with tabs[8]:
        _render_ai_lab(candidates, ticker)
