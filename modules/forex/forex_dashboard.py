# modules/forex/forex_dashboard.py

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False

try:
    from modules.forex.forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
        SUPPORTED_CURRENCIES,
        normalize_pair,
    )
    from modules.forex.forex_ai import (
        ForexAIEngine,
        get_forex_ai_engine,
    )
except Exception:
    from forex_service import (
        ForexService,
        get_forex_service,
        MAJOR_PAIRS,
        CROSS_PAIRS,
        SUPPORTED_CURRENCIES,
        normalize_pair,
    )
    from forex_ai import (
        ForexAIEngine,
        get_forex_ai_engine,
    )


logger = logging.getLogger(__name__)


DEFAULT_PAIRS = MAJOR_PAIRS + CROSS_PAIRS


def _to_dataframe(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _display_table(df: pd.DataFrame, key: str) -> None:
    if df.empty:
        st.info("No data available.")
        return

    if HAS_AGGRID:
        builder = GridOptionsBuilder.from_dataframe(df)
        builder.configure_pagination(enabled=True)
        builder.configure_side_bar()
        builder.configure_default_column(
            resizable=True,
            sortable=True,
            filter=True,
        )
        AgGrid(
            df,
            gridOptions=builder.build(),
            height=420,
            fit_columns_on_grid_load=False,
            key=key,
        )
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def _metric_row(metrics: Dict[str, Any]) -> None:
    columns = st.columns(len(metrics))
    for column, (label, value) in zip(columns, metrics.items()):
        column.metric(label, value)


def _build_services(
    tenant_id: Optional[str],
    user_id: Optional[str],
    db: Any,
    forex_service: Optional[ForexService],
    forex_ai_engine: Optional[ForexAIEngine],
) -> tuple[ForexService, ForexAIEngine]:
    service = forex_service or get_forex_service(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
    )
    engine = forex_ai_engine or get_forex_ai_engine(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
        forex_service=service,
    )
    return service, engine


def render_forex_dashboard(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    forex_ai_engine: Optional[ForexAIEngine] = None,
) -> None:
    service, engine = _build_services(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
        forex_service=forex_service,
        forex_ai_engine=forex_ai_engine,
    )

    st.title("Forex Terminal")
    st.caption("Currency research, AI signals, conversion, scanning, and validation-ready market intelligence.")

    workspace = st.radio(
        "Forex Workspace",
        [
            "Market Overview",
            "AI Signals",
            "Top Opportunities",
            "Currency Converter",
            "Pair Analysis",
            "Market Scanner",
            "Signal History",
            "Model Analytics",
        ],
        horizontal=True,
        key="forex_workspace_radio",
    )

    if workspace == "Market Overview":
        render_market_overview(service)

    elif workspace == "AI Signals":
        render_ai_signals(engine)

    elif workspace == "Top Opportunities":
        render_top_opportunities(engine)

    elif workspace == "Currency Converter":
        render_currency_converter(service)

    elif workspace == "Pair Analysis":
        render_pair_analysis(service, engine)

    elif workspace == "Market Scanner":
        render_market_scanner(engine)

    elif workspace == "Signal History":
        render_signal_history(engine)

    elif workspace == "Model Analytics":
        render_model_analytics(engine)


def render_market_overview(service: ForexService) -> None:
    st.subheader("Market Overview")

    pair_group = st.radio(
        "Pair Group",
        ["Major Pairs", "Cross Pairs", "All Watchlist Pairs"],
        horizontal=True,
        key="forex_market_pair_group",
    )

    if pair_group == "Major Pairs":
        pairs = MAJOR_PAIRS
    elif pair_group == "Cross Pairs":
        pairs = CROSS_PAIRS
    else:
        pairs = DEFAULT_PAIRS

    if st.button("Refresh Market Snapshot", key="forex_refresh_market_snapshot"):
        st.session_state["forex_market_snapshot_requested"] = True

    try:
        snapshot = service.get_market_snapshot(pairs)
        quotes = snapshot.get("pairs", [])
    except Exception as exc:
        st.error(f"Failed to load forex market snapshot: {exc}")
        quotes = []

    df = _to_dataframe(quotes)

    if not df.empty:
        avg_spread = df["spread"].apply(_safe_float).mean() if "spread" in df.columns else 0
        _metric_row(
            {
                "Pairs": len(df),
                "Avg Spread": round(avg_spread, 6),
                "Providers": df["provider"].nunique() if "provider" in df.columns else 0,
                "Updated": datetime.now().strftime("%H:%M:%S"),
            }
        )

        st.markdown("### Live Quotes")
        show_cols = [
            col for col in [
                "pair",
                "price",
                "bid",
                "ask",
                "spread",
                "provider",
                "asof",
            ] if col in df.columns
        ]
        _display_table(df[show_cols], key="forex_market_quotes_grid")

        if "spread" in df.columns:
            spread_df = df[["pair", "spread"]].copy()
            spread_df["spread"] = spread_df["spread"].apply(_safe_float)
            fig = px.bar(
                spread_df,
                x="pair",
                y="spread",
                title="Spread Analysis",
            )
            st.plotly_chart(fig, use_container_width=True)

        if "price" in df.columns:
            heat_df = df[["pair", "price"]].copy()
            heat_df["price"] = heat_df["price"].apply(_safe_float)
            fig = px.treemap(
                heat_df,
                path=["pair"],
                values="price",
                title="Forex Watchlist Heat Map",
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No market data available.")


def render_ai_signals(engine: ForexAIEngine) -> None:
    st.subheader("AI Signals")

    selected_pairs = st.multiselect(
        "Signal Pairs",
        DEFAULT_PAIRS,
        default=MAJOR_PAIRS,
        key="forex_ai_signal_pairs",
    )

    save_signals = st.checkbox(
        "Save Generated Signals",
        value=True,
        key="forex_ai_save_signals",
    )

    if st.button("Generate AI Signals", key="forex_generate_ai_signals"):
        try:
            signals = engine.generate_signals(selected_pairs, save=save_signals)
            rows = [signal.to_dict() for signal in signals]
            st.session_state["forex_ai_signals_rows"] = rows
        except Exception as exc:
            st.error(f"Failed to generate forex AI signals: {exc}")

    rows = st.session_state.get("forex_ai_signals_rows", [])
    df = _to_dataframe(rows)

    if df.empty:
        st.info("Generate AI signals to view recommendations.")
        return

    _metric_row(
        {
            "Signals": len(df),
            "Avg Confidence": round(df["confidence"].apply(_safe_float).mean(), 2),
            "Avg Composite": round(df["composite_score"].apply(_safe_float).mean(), 2),
            "Buy Rated": int(df["recommendation"].isin(["STRONG_BUY", "BUY"]).sum()),
        }
    )

    display_cols = [
        "pair",
        "recommendation",
        "confidence",
        "composite_score",
        "entry_price",
        "stop_price",
        "target_price",
        "risk_reward",
        "trend_score",
        "momentum_score",
        "volatility_score",
        "carry_score",
        "liquidity_score",
        "correlation_score",
        "macro_score",
        "warnings",
    ]
    display_cols = [col for col in display_cols if col in df.columns]
    _display_table(df[display_cols], key="forex_ai_signals_grid")

    fig = px.bar(
        df,
        x="pair",
        y="composite_score",
        color="recommendation",
        title="Composite Score by Pair",
    )
    st.plotly_chart(fig, use_container_width=True)

    fig = px.scatter(
        df,
        x="confidence",
        y="risk_reward",
        color="recommendation",
        hover_data=["pair"],
        title="Confidence vs Risk Reward",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_top_opportunities(engine: ForexAIEngine) -> None:
    st.subheader("Top Forex Opportunities")

    col1, col2, col3 = st.columns(3)

    min_confidence = col1.slider(
        "Minimum Confidence",
        min_value=0,
        max_value=100,
        value=65,
        step=1,
        key="forex_top_min_confidence",
    )

    min_risk_reward = col2.slider(
        "Minimum Risk Reward",
        min_value=0.0,
        max_value=5.0,
        value=1.5,
        step=0.1,
        key="forex_top_min_rr",
    )

    limit = col3.number_input(
        "Opportunity Limit",
        min_value=1,
        max_value=50,
        value=10,
        step=1,
        key="forex_top_limit",
    )

    if st.button("Find Top Opportunities", key="forex_find_top_opportunities"):
        try:
            opportunities = engine.get_top_opportunities(
                DEFAULT_PAIRS,
                min_confidence=float(min_confidence),
                min_risk_reward=float(min_risk_reward),
                limit=int(limit),
                save=True,
            )
            st.session_state["forex_top_opportunities_rows"] = [
                item.to_dict() for item in opportunities
            ]
        except Exception as exc:
            st.error(f"Failed to find top forex opportunities: {exc}")

    rows = st.session_state.get("forex_top_opportunities_rows", [])
    df = _to_dataframe(rows)

    if df.empty:
        st.info("Run the opportunity scan to view ranked pairs.")
        return

    _metric_row(
        {
            "Strong Buy": int((df["recommendation"] == "STRONG_BUY").sum()),
            "Buy": int((df["recommendation"] == "BUY").sum()),
            "Avg Confidence": round(df["confidence"].apply(_safe_float).mean(), 2),
            "Avg Risk Reward": round(df["risk_reward"].apply(_safe_float).mean(), 2),
        }
    )

    display_cols = [
        "pair",
        "recommendation",
        "confidence",
        "composite_score",
        "entry_price",
        "stop_price",
        "target_price",
        "risk_reward",
        "rationale",
        "warnings",
    ]
    display_cols = [col for col in display_cols if col in df.columns]
    _display_table(df[display_cols], key="forex_top_opportunities_grid")

    fig = px.bar(
        df,
        x="pair",
        y="confidence",
        color="recommendation",
        title="Top Opportunity Confidence",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_currency_converter(service: ForexService) -> None:
    st.subheader("Currency Converter")

    col1, col2, col3 = st.columns(3)

    amount = col1.number_input(
        "Amount",
        min_value=0.0,
        value=1000.0,
        step=100.0,
        key="forex_converter_amount",
    )

    from_currency = col2.selectbox(
        "From Currency",
        SUPPORTED_CURRENCIES,
        index=SUPPORTED_CURRENCIES.index("USD") if "USD" in SUPPORTED_CURRENCIES else 0,
        key="forex_converter_from_currency",
    )

    to_currency = col3.selectbox(
        "To Currency",
        SUPPORTED_CURRENCIES,
        index=SUPPORTED_CURRENCIES.index("EUR") if "EUR" in SUPPORTED_CURRENCIES else 0,
        key="forex_converter_to_currency",
    )

    if st.button("Convert Currency", key="forex_convert_currency"):
        try:
            result = service.convert(
                amount=float(amount),
                from_currency=from_currency,
                to_currency=to_currency,
            )
            st.session_state["forex_conversion_result"] = result
        except Exception as exc:
            st.error(f"Currency conversion failed: {exc}")

    result = st.session_state.get("forex_conversion_result")

    if result:
        _metric_row(
            {
                "Rate": round(_safe_float(result.get("rate")), 6),
                "Converted Amount": round(_safe_float(result.get("converted_amount")), 2),
                "From": result.get("from_currency"),
                "To": result.get("to_currency"),
            }
        )

        st.json(result)


def render_pair_analysis(service: ForexService, engine: ForexAIEngine) -> None:
    st.subheader("Pair Analysis")

    selected_pair = st.selectbox(
        "Analysis Pair",
        DEFAULT_PAIRS,
        index=0,
        key="forex_pair_analysis_pair",
    )

    save_signal = st.checkbox(
        "Save Pair Signal",
        value=True,
        key="forex_pair_analysis_save_signal",
    )

    if st.button("Analyze Pair", key="forex_analyze_pair"):
        try:
            pair = normalize_pair(selected_pair)
            quote = service.get_quote(pair)
            signal = engine.generate_signal(pair, save=save_signal)

            st.session_state["forex_pair_analysis_quote"] = quote.to_dict()
            st.session_state["forex_pair_analysis_signal"] = signal.to_dict()
        except Exception as exc:
            st.error(f"Pair analysis failed: {exc}")

    quote_row = st.session_state.get("forex_pair_analysis_quote")
    signal_row = st.session_state.get("forex_pair_analysis_signal")

    if not quote_row or not signal_row:
        st.info("Run pair analysis to view quote, AI scorecard, and risk profile.")
        return

    st.markdown("### Quote")
    _metric_row(
        {
            "Pair": quote_row.get("pair"),
            "Price": round(_safe_float(quote_row.get("price")), 6),
            "Bid": round(_safe_float(quote_row.get("bid")), 6),
            "Ask": round(_safe_float(quote_row.get("ask")), 6),
        }
    )

    st.markdown("### AI Scorecard")
    _metric_row(
        {
            "Recommendation": signal_row.get("recommendation"),
            "Confidence": round(_safe_float(signal_row.get("confidence")), 2),
            "Composite": round(_safe_float(signal_row.get("composite_score")), 2),
            "Risk Reward": round(_safe_float(signal_row.get("risk_reward")), 2),
        }
    )

    score_fields = [
        "trend_score",
        "momentum_score",
        "volatility_score",
        "carry_score",
        "liquidity_score",
        "correlation_score",
        "macro_score",
    ]

    score_df = pd.DataFrame(
        {
            "score": [field.replace("_score", "").replace("_", " ").title() for field in score_fields],
            "value": [_safe_float(signal_row.get(field)) for field in score_fields],
        }
    )

    fig = px.bar(
        score_df,
        x="score",
        y="value",
        title="AI Score Breakdown",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Trade Levels")
    level_df = pd.DataFrame(
        [
            {
                "pair": signal_row.get("pair"),
                "entry": signal_row.get("entry_price"),
                "stop": signal_row.get("stop_price"),
                "target": signal_row.get("target_price"),
                "risk_reward": signal_row.get("risk_reward"),
            }
        ]
    )
    _display_table(level_df, key="forex_pair_trade_levels_grid")

    st.markdown("### Rationale")
    st.write(signal_row.get("rationale", ""))

    warnings = signal_row.get("warnings")
    if warnings:
        st.warning(warnings)


def render_market_scanner(engine: ForexAIEngine) -> None:
    st.subheader("Market Scanner")

    col1, col2, col3 = st.columns(3)

    min_confidence = col1.slider(
        "Scanner Minimum Confidence",
        min_value=0,
        max_value=100,
        value=60,
        step=1,
        key="forex_scanner_min_confidence",
    )

    min_risk_reward = col2.slider(
        "Scanner Minimum Risk Reward",
        min_value=0.0,
        max_value=5.0,
        value=1.2,
        step=0.1,
        key="forex_scanner_min_rr",
    )

    recommendation_filter = col3.selectbox(
        "Recommendation Filter",
        ["ALL", "STRONG_BUY", "BUY", "WATCH", "REDUCE", "SELL"],
        key="forex_scanner_recommendation_filter",
    )

    selected_pairs = st.multiselect(
        "Scanner Pairs",
        DEFAULT_PAIRS,
        default=DEFAULT_PAIRS,
        key="forex_scanner_pairs",
    )

    if st.button("Run Forex Scanner", key="forex_run_market_scanner"):
        try:
            signals = engine.generate_signals(selected_pairs, save=True)
            rows = [signal.to_dict() for signal in signals]
            st.session_state["forex_scanner_rows"] = rows
        except Exception as exc:
            st.error(f"Forex scanner failed: {exc}")

    rows = st.session_state.get("forex_scanner_rows", [])
    df = _to_dataframe(rows)

    if df.empty:
        st.info("Run scanner to view filtered results.")
        return

    df = df[
        (df["confidence"].apply(_safe_float) >= float(min_confidence))
        & (df["risk_reward"].apply(_safe_float) >= float(min_risk_reward))
    ]

    if recommendation_filter != "ALL":
        df = df[df["recommendation"] == recommendation_filter]

    _display_table(df, key="forex_market_scanner_grid")


def render_signal_history(engine: ForexAIEngine) -> None:
    st.subheader("Signal History")

    col1, col2 = st.columns(2)

    selected_pair = col1.selectbox(
        "History Pair",
        ["ALL"] + DEFAULT_PAIRS,
        key="forex_history_pair",
    )

    limit = col2.number_input(
        "History Limit",
        min_value=10,
        max_value=1000,
        value=100,
        step=10,
        key="forex_history_limit",
    )

    if st.button("Load Signal History", key="forex_load_signal_history"):
        try:
            pair = None if selected_pair == "ALL" else selected_pair
            rows = engine.load_signal_history(pair=pair, limit=int(limit))
            st.session_state["forex_signal_history_rows"] = rows
        except Exception as exc:
            st.error(f"Failed to load signal history: {exc}")

    rows = st.session_state.get("forex_signal_history_rows", [])
    df = _to_dataframe(rows)

    if df.empty:
        st.info("No signal history loaded.")
        return

    _display_table(df, key="forex_signal_history_grid")

    if "recommendation" in df.columns:
        fig = px.histogram(
            df,
            x="recommendation",
            title="Recommendation Distribution",
        )
        st.plotly_chart(fig, use_container_width=True)

    if "confidence" in df.columns:
        fig = px.histogram(
            df,
            x="confidence",
            title="Confidence Distribution",
        )
        st.plotly_chart(fig, use_container_width=True)

    if "asof" in df.columns and "composite_score" in df.columns:
        trend_df = df.copy()
        trend_df["asof"] = pd.to_datetime(trend_df["asof"], errors="coerce")
        trend_df["composite_score"] = trend_df["composite_score"].apply(_safe_float)
        trend_df = trend_df.dropna(subset=["asof"])

        if not trend_df.empty:
            fig = px.line(
                trend_df.sort_values("asof"),
                x="asof",
                y="composite_score",
                color="pair" if "pair" in trend_df.columns else None,
                title="Composite Score Trend",
            )
            st.plotly_chart(fig, use_container_width=True)


def render_model_analytics(engine: ForexAIEngine) -> None:
    st.subheader("Model Analytics")

    if st.button("Generate Model Snapshot", key="forex_generate_model_snapshot"):
        try:
            engine.save_model_snapshot()
            st.success("Forex model snapshot saved.")
        except Exception as exc:
            st.error(f"Failed to save model snapshot: {exc}")

    try:
        signals = engine.generate_signals(MAJOR_PAIRS, save=False)
        rows = [signal.to_dict() for signal in signals]
    except Exception as exc:
        st.error(f"Failed to generate model analytics: {exc}")
        rows = []

    df = _to_dataframe(rows)

    if df.empty:
        st.info("No model analytics available.")
        return

    _metric_row(
        {
            "Signals Analyzed": len(df),
            "Average Confidence": round(df["confidence"].apply(_safe_float).mean(), 2),
            "Average Composite": round(df["composite_score"].apply(_safe_float).mean(), 2),
            "Average Risk Reward": round(df["risk_reward"].apply(_safe_float).mean(), 2),
        }
    )

    recommendation_counts = (
        df.groupby("recommendation")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
    )

    fig = px.pie(
        recommendation_counts,
        names="recommendation",
        values="count",
        title="Recommendation Breakdown",
    )
    st.plotly_chart(fig, use_container_width=True)

    score_fields = [
        "trend_score",
        "momentum_score",
        "volatility_score",
        "carry_score",
        "liquidity_score",
        "correlation_score",
        "macro_score",
        "composite_score",
        "confidence",
    ]

    score_summary = pd.DataFrame(
        [
            {
                "score": field.replace("_score", "").replace("_", " ").title(),
                "average": round(df[field].apply(_safe_float).mean(), 2),
            }
            for field in score_fields
            if field in df.columns
        ]
    )

    fig = px.bar(
        score_summary,
        x="score",
        y="average",
        title="Average Model Scores",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Model Weighting")
    weights = pd.DataFrame(
        [
            {"factor": "Trend", "weight": 0.22},
            {"factor": "Momentum", "weight": 0.18},
            {"factor": "Volatility", "weight": 0.13},
            {"factor": "Carry", "weight": 0.12},
            {"factor": "Liquidity", "weight": 0.15},
            {"factor": "Correlation", "weight": 0.10},
            {"factor": "Macro", "weight": 0.10},
        ]
    )
    _display_table(weights, key="forex_model_weights_grid")


def render(
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Any = None,
    forex_service: Optional[ForexService] = None,
    forex_ai_engine: Optional[ForexAIEngine] = None,
) -> None:
    render_forex_dashboard(
        tenant_id=tenant_id,
        user_id=user_id,
        db=db,
        forex_service=forex_service,
        forex_ai_engine=forex_ai_engine,
    )