"""
modules/options/options_learning_dashboard.py

Phase 8 — Options Learning & Performance Intelligence Dashboard.
Adds closed-loop learning after analysis, strategy selection, portfolio risk,
and execution automation.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from modules.options.options_performance_ledger import (
    get_performance_records,
    record_trade_outcome,
    seed_sample_outcomes,
)
from modules.options.options_trade_outcome_analyzer import analyze_trade_outcomes, equity_curve, outcome_frame
from modules.options.options_strategy_attribution_engine import strategy_attribution, tag_attribution
from modules.options.options_learning_engine import generate_learning_report
from modules.options.options_model_scorecard import build_model_scorecard, model_improvement_actions
from modules.options.options_feedback_optimizer import optimize_strategy_weights
from modules.options.options_replay_engine import replay_batch, build_trade_replay
from modules.options.options_learning_ai import explain_learning_report


def render_options_learning_dashboard(ticker: str, paper: bool = True):
    st.subheader(f"📚 Learning & Performance Intelligence — {ticker.upper()}")
    st.caption("Closed-loop learning · post-trade replay · AI model scorecard · strategy attribution · feedback optimizer")

    c1, c2, c3 = st.columns([1, 1, 4])
    with c1:
        if st.button("Seed Sample Outcomes", key=f"learning_seed_{ticker}", use_container_width=True):
            seed_sample_outcomes(ticker)
    with c2:
        show_all = st.toggle("All Tickers", value=False, key=f"learning_all_{ticker}")

    records = get_performance_records(None if show_all else ticker)
    report = generate_learning_report(records)
    summary = report.get("summary", {})
    scorecard = build_model_scorecard(records)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Trades", summary.get("trade_count", 0))
    m2.metric("Win Rate", f"{summary.get('win_rate', 0):.1f}%")
    m3.metric("Total P/L", f"${summary.get('total_pnl', 0):,.0f}")
    m4.metric("Profit Factor", summary.get("profit_factor", 0))
    m5.metric("AI Accuracy", f"{scorecard.get('accuracy', 0):.1f}%")

    tabs = st.tabs([
        "📊 Outcome Ledger",
        "📈 Equity Curve",
        "🎯 Strategy Attribution",
        "🧠 Learning Report",
        "🤖 Model Scorecard",
        "🔁 Replay",
        "⚙ Feedback Optimizer",
    ])

    with tabs[0]:
        st.markdown("#### Add / Review Trade Outcome")
        with st.form(f"learning_add_{ticker}"):
            a, b, c, d, e = st.columns(5)
            strategy = a.text_input("Strategy", value="Bull Put Spread")
            thesis = b.text_input("Thesis", value="Dealer support + premium flow")
            entry = c.number_input("Entry", 0.0, 9999.0, 1.00, 0.05)
            exit_ = d.number_input("Exit", 0.0, 9999.0, 0.50, 0.05)
            qty = e.number_input("Qty", 1, 1000, 1)
            tags = st.multiselect("Tags", ["smart_money", "dealer", "volatility", "earnings", "income", "hedge", "autopilot"], default=["smart_money"])
            submitted = st.form_submit_button("Record Outcome")
            if submitted:
                record_trade_outcome(ticker, strategy, thesis, entry, exit_, int(qty), "closed", "manual", tags)
                st.success("Outcome recorded.")
        df = outcome_frame(get_performance_records(None if show_all else ticker))
        if df.empty:
            st.info("No outcomes recorded yet. Use Seed Sample Outcomes or add a trade outcome.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[1]:
        curve = equity_curve(records)
        if curve.empty:
            st.info("No equity curve yet.")
        else:
            st.line_chart(curve.set_index("trade_number")[["cumulative_pnl"]])
            st.dataframe(curve, use_container_width=True, hide_index=True)

    with tabs[2]:
        strat = strategy_attribution(records)
        tags = tag_attribution(records)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### By Strategy")
            st.dataframe(strat, use_container_width=True, hide_index=True)
        with c2:
            st.markdown("#### By Signal Tag")
            st.dataframe(tags, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.markdown("#### Lessons")
        for lesson in report.get("lessons", []):
            st.info(lesson)
        if st.button("Generate AI Learning Commentary", key=f"learning_ai_{ticker}", type="primary"):
            st.markdown(explain_learning_report(report))

    with tabs[4]:
        st.markdown("#### AI Recommendation Scorecard")
        c1, c2, c3 = st.columns(3)
        c1.metric("Recommendations", scorecard.get("recommendations", 0))
        c2.metric("Accuracy", f"{scorecard.get('accuracy', 0):.1f}%")
        c3.metric("Avg P/L", f"${scorecard.get('avg_pnl', 0):,.0f}")
        st.success(scorecard.get("status", "No status"))
        for action in model_improvement_actions(scorecard):
            st.warning(action)

    with tabs[5]:
        st.markdown("#### Trade Replay")
        replays = replay_batch(records, limit=10)
        if not replays:
            st.info("No trades to replay.")
        for rep in replays:
            with st.expander(f"{rep.get('ticker')} · {rep.get('strategy')} · {rep.get('outcome')} · P/L ${rep.get('pnl'):,.0f}"):
                st.write(rep.get("diagnosis"))
                st.markdown("**Review questions**")
                for q in rep.get("review_questions", []):
                    st.markdown(f"- {q}")

    with tabs[6]:
        st.markdown("#### Feedback Optimizer")
        weights = optimize_strategy_weights(report)
        if weights:
            st.dataframe(pd.DataFrame(weights), use_container_width=True, hide_index=True)
        else:
            st.info("No attribution yet. Record outcomes to generate feedback weights.")
