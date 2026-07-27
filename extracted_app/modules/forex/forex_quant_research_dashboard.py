"""
Forex Quant Research Dashboard - Sprint 25 Phase 3

Streamlit UI for live quant research integration.
Preserves StockApp patterns: tenant-aware, DB-aware, graceful fallbacks, no empty widget labels.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.forex.forex_quant_research_engine import (
    DEFAULT_PAIRS,
    ForexQuantResearchEngine,
    ensure_forex_quant_research_tables,
)


def _get_context_value(name: str, default: Optional[str] = None) -> Optional[str]:
    for key in (name, name.upper(), name.lower()):
        if key in st.session_state and st.session_state.get(key) is not None:
            return str(st.session_state.get(key))
    user = st.session_state.get("user") or st.session_state.get("current_user") or {}
    if isinstance(user, dict):
        if name in user and user.get(name) is not None:
            return str(user.get(name))
        if name == "user_id" and user.get("id") is not None:
            return str(user.get("id"))
    return default


def _get_db_session(explicit_db: Any = None) -> Any:
    if explicit_db is not None:
        return explicit_db
    for key in ("db", "db_session", "session"):
        if key in st.session_state and st.session_state.get(key) is not None:
            return st.session_state.get(key)
    try:
        from db import get_db_session  # type: ignore
        return get_db_session()
    except Exception:
        return None





def render_forex_quant_research_dashboard(db: Any = None, market_data: Any = None, tenant_id: Optional[str] = None, user_id: Optional[str] = None, portfolio_id: Optional[str] = None) -> None:
    st.subheader("Live Quant Research")
    st.caption("Sprint 25 Phase 3 — tenant-aware live forex quant research with Postgres persistence.")
    data_source = st.radio(
        "Historical Data Source",
        [
            "Live Providers",
            "PostgreSQL",
            "Upload CSV",
        ],
        horizontal=True,
    )

    selected_interval = st.selectbox(
        "Historical Interval",
        [
            "1day",
            "1hour",
            "30min",
            "15min",
            "5min",
            "1min",
        ],
        index=0,
    )

    uploaded = st.file_uploader(
        "Optional Historical FX CSV",
        type=["csv"],
    )
    tenant_id = tenant_id or _get_context_value("tenant_id", "default")
    user_id = user_id or _get_context_value("user_id")
    portfolio_id = portfolio_id or _get_context_value("portfolio_id")
    db = _get_db_session(db)

    selected_pairs = st.multiselect(
        "Research Universe",
        options=list(DEFAULT_PAIRS),
        default=list(DEFAULT_PAIRS[:10]),
        help="Forex pairs to analyze using live market data and persisted research history.",
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        persist = st.toggle("Persist to Postgres", value=True, help="Save snapshots and pair-level signals to tenant-aware Postgres tables.")
    with col_b:
        use_service = st.toggle("Load from Forex Service", value=market_data is None, help="Use existing modules.forex.forex_service adapters when available.")
    with col_c:
        limit = st.number_input("Signal Rows", min_value=10, max_value=250, value=50, step=10)

    engine = ForexQuantResearchEngine(db=db, tenant_id=tenant_id, user_id=user_id, portfolio_id=portfolio_id)

    if db is not None:
        try:
            ensure_forex_quant_research_tables(db)
            st.success("Postgres persistence is ready for forex quant research.")
        except Exception as exc:
            st.warning(f"Postgres table initialization failed: {exc}")

    run_col, load_col = st.columns(2)
    run_clicked = run_col.button("Run Live Quant Research", type="primary", use_container_width=True)
    load_clicked = load_col.button("Load Latest Saved Research", use_container_width=True)

    result = None
    if run_clicked:
        live_data = market_data
        if use_service and live_data is None:
            from modules.forex.forex_service import get_forex_service

            service = get_forex_service(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                portfolio_id=portfolio_id,
            )

            history_service = service.get_history_service()

            market_data = history_service.get_market_data(
                source=data_source,
                pairs=selected_pairs,
                uploaded_file=uploaded,
                interval=selected_interval,
                backfill_days=365 * 3,
            )

            result = engine.run_research(
                market_data=market_data,
                pairs=selected_pairs,
                persist=bool(persist and db is not None),
            )
        st.session_state["forex_quant_research_result"] = result
        if load_clicked:

            result = engine.load_latest(limit=int(limit))

        elif run_clicked:

            market_data = history_service.get_market_data(
                source=data_source,
                pairs=selected_pairs,
                uploaded_file=uploaded,
                interval=selected_interval,
                backfill_days=365 * 3,
            )

            result = engine.run_research(
                market_data=market_data,
                pairs=selected_pairs,
                persist=bool(persist and db is not None),
            )
        st.session_state["forex_quant_research_result"] = result
    else:
        result = st.session_state.get("forex_quant_research_result")
        if result is None and db is not None:
            try:
                result = engine.load_latest(limit=int(limit))
            except Exception:
                result = None

    if not result:
        st.info("Run live quant research or load the latest saved tenant snapshot.")
        return

    snapshot = result.get("snapshot") or {}
    signals = result.get("signals") or []
    data_status = result.get("data_status", "UNKNOWN")

    if data_status in {"NO_DATA", "NO_DB_SESSION", "DB_EMPTY"}:
        st.warning(snapshot.get("research_summary") or "No quant research output is available yet.")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Analyzed Pairs", snapshot.get("analyzed_pairs", 0))
    metric_cols[1].metric("Avg Quant Score", f"{float(snapshot.get('avg_quant_score') or 0):.1f}")
    metric_cols[2].metric("Bullish", snapshot.get("bullish_count", 0))
    metric_cols[3].metric("Bearish", snapshot.get("bearish_count", 0))
    metric_cols[4].metric("Risk Regime", snapshot.get("risk_regime") or "N/A")

    st.info(snapshot.get("research_summary") or "Quant research completed.")

    if signals:
        df = pd.DataFrame(signals)
        preferred_cols = [
            "symbol", "signal", "conviction", "quant_score", "close", "return_1d", "return_5d", "return_20d",
            "volatility_20d", "momentum_score", "mean_reversion_score", "carry_score", "breakout_score",
            "trend_quality_score", "correlation_risk_score", "rationale",
        ]
        visible_cols = [c for c in preferred_cols if c in df.columns]
        st.dataframe(df[visible_cols], use_container_width=True, hide_index=True)

        chart_cols = [c for c in ["quant_score", "momentum_score", "trend_quality_score", "correlation_risk_score"] if c in df.columns]
        if chart_cols:
            chart_df = df.set_index("symbol")[chart_cols].head(20)
            st.bar_chart(chart_df)
    else:
        st.info("No pair-level quant signals were produced from the available live input.")


# Compatibility aliases used by different StockApp dashboard loaders.
def render(db: Any = None, **kwargs: Any) -> None:
    render_forex_quant_research_dashboard(db=db, **kwargs)


def render_dashboard(db: Any = None, **kwargs: Any) -> None:
    render_forex_quant_research_dashboard(db=db, **kwargs)
