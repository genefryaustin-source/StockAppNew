# modules/forex/forex_trader_command_center.py

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

try:
    import plotly.express as px
except Exception:
    px = None

try:
    from modules.forex.forex_service import MAJOR_PAIRS, CROSS_PAIRS
except Exception:
    MAJOR_PAIRS = [
        "EUR/USD",
        "GBP/USD",
        "USD/JPY",
        "USD/CHF",
        "AUD/USD",
        "NZD/USD",
        "USD/CAD",
    ]
    CROSS_PAIRS = [
        "EUR/JPY",
        "GBP/JPY",
        "AUD/JPY",
        "EUR/GBP",
        "EUR/CHF",
    ]

from modules.forex.forex_trader_command_center_engine import (
    DEFAULT_PAIRS,
    get_forex_trader_command_center_engine,
)


def _metric_card(label: str, value: Any, help_text: Optional[str] = None) -> None:
    st.metric(label, value, help=help_text)


def _score_badge(score: Any) -> str:
    try:
        score_float = float(score)
    except Exception:
        score_float = 0.0

    if score_float >= 85:
        return "🟢"
    if score_float >= 65:
        return "🟡"
    if score_float >= 45:
        return "🟠"
    return "🔴"


def _bar(score: Any) -> None:
    try:
        value = max(0.0, min(100.0, float(score)))
    except Exception:
        value = 0.0
    st.progress(value / 100.0)


def _dataframe(rows: List[Dict[str, Any]], key: str, height: int = 300) -> None:
    if not rows:
        st.info("No data available.")
        return
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def _render_market_regime(data: Dict[str, Any]) -> None:
    st.subheader("Market Regime")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Risk Regime", data.get("risk_label", "Neutral"))
    c2.metric("USD Strength", f"{data.get('usd_strength', 50)}")
    c3.metric("Volatility", data.get("volatility", "Medium"))
    c4.metric("Liquidity", data.get("liquidity", "Normal"))
    c5.metric("Macro Score", f"{data.get('macro_score', 0)}")

    if data.get("warning"):
        st.caption(f"Warning: {data['warning']}")


def _render_currency_strength(data: Dict[str, Any]) -> None:
    st.subheader("Currency Strength")

    rows = data.get("rows", [])

    if not rows:
        st.info("Currency strength data is unavailable.")
        return

    left, right = st.columns([1, 1])

    with left:
        for row in rows[:8]:
            currency = row.get("currency", "")
            score = row.get("score", row.get("strength_score", 0))
            st.write(f"{_score_badge(score)} **{currency}** — {round(float(score or 0), 2)}")
            _bar(score)

    with right:
        if px is not None:
            df = pd.DataFrame(rows[:8])
            if "score" in df.columns:
                y_col = "currency"
                x_col = "score"
            else:
                y_col = "currency"
                x_col = "strength_score"
            fig = px.bar(
                df,
                x=x_col,
                y=y_col,
                orientation="h",
                title="Currency Strength Ranking",
            )
            fig.update_layout(height=360, margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else:
            _dataframe(rows[:8], "fx_strength_rows", height=360)


def _render_opportunities(rows: List[Dict[str, Any]]) -> None:
    st.subheader("Top Opportunities")

    if not rows:
        st.info("No trade opportunities available.")
        return

    display_cols = [
        "pair",
        "recommendation",
        "conviction_score",
        "confidence_score",
        "risk_reward",
        "entry_price",
        "stop_price",
        "target_price",
    ]

    df = pd.DataFrame(rows)
    cols = [col for col in display_cols if col in df.columns]
    st.dataframe(
        df[cols],
        use_container_width=True,
        hide_index=True,
        height=300,
    )

    top = rows[0]
    with st.expander(f"Why {top.get('recommendation', 'WATCH')} {top.get('pair', '')}?", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Conviction", top.get("conviction_score", 0))
        c2.metric("Confidence", top.get("confidence_score", 0))
        c3.metric("Risk / Reward", top.get("risk_reward", 0))
        c4.metric("Signal", top.get("signal", top.get("recommendation", "WATCH")))

        rationale = top.get("rationale")
        warnings = top.get("warnings")

        if rationale:
            st.write(rationale)
        if warnings:
            st.warning(warnings)


def _render_institutional_flow(data: Dict[str, Any]) -> None:
    st.subheader("Institutional Flow")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Smart Money Bias", data.get("smart_money_bias", "Neutral"))
    c2.metric("Top Pair", data.get("top_pair", "N/A"))
    c3.metric("Avg Score", data.get("average_score", 0))
    c4.metric("Avg Confidence", data.get("average_confidence", 0))

    c1, c2, c3 = st.columns(3)
    c1.metric("Long Setups", data.get("long_count", 0))
    c2.metric("Short Setups", data.get("short_count", 0))
    c3.metric("Watch", data.get("watch_count", 0))

    rows = data.get("rows", [])
    if rows:
        with st.expander("Institutional Detail", expanded=False):
            _dataframe(rows, "fx_institutional_rows")


def _render_carry_trades(data: Dict[str, Any]) -> None:
    st.subheader("Carry Trades")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Highest Yield", data.get("highest_yield", "N/A"))
    c2.metric("Lowest Yield", data.get("lowest_yield", "N/A"))
    c3.metric("Funding Currency", data.get("funding_currency", "N/A"))
    c4.metric("Expected Return", data.get("expected_return", 0))

    rows = data.get("rows", [])
    if rows:
        with st.expander("Carry Trade Detail", expanded=False):
            _dataframe(rows, "fx_carry_rows")


def _render_central_banks(data: Dict[str, Any]) -> None:
    st.subheader("Central Banks")

    rows = data.get("rows", [])
    if not rows:
        st.info("Central bank data unavailable.")
        return

    columns = st.columns(4)
    for index, row in enumerate(rows[:8]):
        with columns[index % 4]:
            st.metric(
                row.get("currency", "N/A"),
                row.get("bank", "Central Bank"),
                delta=f"Rate {row.get('rate', 0)} | Hawkish {row.get('hawkish_score', 0)}",
            )


def _render_events(data: Dict[str, Any]) -> None:
    st.subheader("Upcoming Events")
    _dataframe(data.get("rows", []), "fx_events", height=220)


def _render_ai(data: Dict[str, Any]) -> None:
    st.subheader("AI Recommendation Engine")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Best Trade", data.get("best_trade", "N/A"))
    c2.metric("Recommendation", data.get("recommendation", "N/A"))
    c3.metric("Confidence", data.get("confidence", 0))
    c4.metric("Risk / Reward", data.get("risk_reward", 0))

    c1, c2, c3 = st.columns(3)
    c1.metric("Entry", data.get("entry", 0))
    c2.metric("Stop", data.get("stop", 0))
    c3.metric("Target", data.get("target", 0))

    if data.get("rationale"):
        st.write(data["rationale"])
    if data.get("warnings"):
        st.warning(data["warnings"])


def _render_portfolio(data: Dict[str, Any]) -> None:
    st.subheader("Portfolio")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Trades", data.get("open_trades", 0))
    c2.metric("Exposure", data.get("exposure", 0))
    c3.metric("P/L", data.get("pnl", 0))
    c4.metric("Risk Score", data.get("risk_score", 0))

    rows = data.get("rows", [])
    if rows:
        with st.expander("Portfolio Allocation Detail", expanded=False):
            _dataframe(rows, "fx_portfolio_rows")


def _render_paper_trading(data: Dict[str, Any]) -> None:
    st.subheader("Paper Trading")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Orders", data.get("orders", 0))
    c2.metric("Positions", data.get("positions", 0))
    c3.metric("History", data.get("history", 0))
    perf = data.get("performance", {})
    c4.metric("Win Rate", perf.get("win_rate", 0))

    if data.get("message"):
        st.caption(data["message"])


def render_forex_trader_command_center(
    db=None,
    user=None,
    tenant_id=None,
    portfolio_id=None,
) -> Dict[str, Any]:
    st.title("Forex Command Center")
    st.caption(
        "Trader-facing workspace for market regime, currency strength, opportunities, institutional flow, central banks, carry trades, portfolio, and paper trading."
    )

    all_pairs = list(dict.fromkeys((MAJOR_PAIRS or []) + (CROSS_PAIRS or []) + DEFAULT_PAIRS))

    with st.sidebar:
        st.markdown("### Forex Command Center")
        selected_pairs = st.multiselect(
            "Pairs",
            all_pairs,
            default=DEFAULT_PAIRS[:8],
            key="fx_command_center_pairs",
        )
        save_results = st.checkbox(
            "Persist scan results",
            value=False,
            key="fx_command_center_save",
        )
        refresh = st.button(
            "Refresh Forex Command Center",
            key="fx_command_center_refresh",
        )

    cache_key = "forex_trader_command_center_payload"

    if refresh or cache_key not in st.session_state:
        with st.spinner("Building Forex Command Center..."):
            st.session_state[cache_key] = get_forex_trader_command_center_engine().build_dashboard(
                pairs=selected_pairs or DEFAULT_PAIRS,
                portfolio_id=portfolio_id,
                save=save_results,
            )

    payload = st.session_state.get(cache_key, {})

    warnings = payload.get("warnings", [])
    if warnings:
        with st.expander("Command Center Warnings", expanded=False):
            for warning in warnings[:10]:
                st.warning(warning)

    _render_market_regime(payload.get("market_regime", {}))

    st.divider()

    left, right = st.columns([1, 1])
    with left:
        _render_currency_strength(payload.get("currency_strength", {}))
    with right:
        _render_ai(payload.get("ai_recommendation", {}))

    st.divider()

    _render_opportunities(payload.get("top_opportunities", []))

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_institutional_flow(payload.get("institutional_flow", {}))
    with c2:
        _render_carry_trades(payload.get("carry_trades", {}))

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_central_banks(payload.get("central_banks", {}))
    with c2:
        _render_events(payload.get("upcoming_events", {}))

    st.divider()

    c1, c2 = st.columns(2)
    with c1:
        _render_portfolio(payload.get("portfolio", {}))
    with c2:
        _render_paper_trading(payload.get("paper_trading", {}))

    with st.expander("Raw Command Center Payload", expanded=False):
        st.json(payload)

    return payload
