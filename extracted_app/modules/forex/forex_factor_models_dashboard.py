"""
Forex Factor Models Dashboard - Sprint 25 Phase 4

Streamlit UI for live factor model integration.
Preserves StockApp patterns: tenant-aware, DB-aware, radio-safe labels, graceful fallbacks.
"""

from __future__ import annotations


from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from modules.forex.forex_factor_models_engine import (
    DEFAULT_PAIRS,
    FACTOR_WEIGHTS,
    ForexFactorModelsEngine,
    ensure_forex_factor_model_tables,
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
        if name == "tenant_id" and user.get("tenant_id") is not None:
            return str(user.get("tenant_id"))
    return default


def _safe_metric(value: Any, suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        if isinstance(value, float):
            return f"{value:,.2f}{suffix}"
        return f"{value}{suffix}"
    except Exception:
        return "—"








def _render_snapshot(snapshot: Optional[Dict[str, Any]]) -> None:
    if not snapshot:
        st.info("No factor model snapshot is available yet.")
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Analyzed Pairs", _safe_metric(snapshot.get("analyzed_pairs")))
    col2.metric("Average Factor Score", _safe_metric(snapshot.get("avg_factor_score")))
    col3.metric("Top Pair", snapshot.get("top_factor_pair") or "—")
    col4.metric("Regime", snapshot.get("factor_regime") or "—")
    st.caption(snapshot.get("summary") or "")


def _render_factor_weights() -> None:
    weights_df = pd.DataFrame([
        {"factor": k.replace("_", " ").title(), "weight": v}
        for k, v in FACTOR_WEIGHTS.items()
    ])
    st.dataframe(weights_df, use_container_width=True, hide_index=True)


def render_forex_factor_models_dashboard(
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    service: Any = None,
    runtime: Any = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Render the Sprint 25 Phase 4 live factor model dashboard."""
    tenant_id = str(tenant_id or _get_context_value("tenant_id") or "default")
    user_id = str(user_id or _get_context_value("user_id") or "") or None
    portfolio_id = str(portfolio_id or _get_context_value("portfolio_id") or "") or None

    st.subheader("Forex Factor Models")
    st.caption("Sprint 25 Phase 4 — live, tenant-aware multi-factor ranking and signal generation.")
    engine = ForexFactorModelsEngine(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )
    data_source = st.radio(
        "Historical Data Source",
        [
            "Live Providers",
            "PostgreSQL",
            "Upload CSV",
        ],
        horizontal=True,
    )

    if db is not None:
        try:
            ensure_forex_factor_model_tables(db)
        except Exception as exc:
            st.warning(f"Factor model schema initialization warning: {exc}")

    with st.expander("Factor Model Controls", expanded=True):

        selected_pairs = st.multiselect(
            "Factor Universe",
            options=list(DEFAULT_PAIRS),
            default=list(DEFAULT_PAIRS[:10]),
        )

        persist = st.checkbox(
            "Persist factor model results to Postgres",
            value=db is not None,
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

        use_db_latest = st.checkbox(
            "Load latest saved factor model snapshot",
            value=False,
        )

        uploaded = st.file_uploader(
            "Optional live/history CSV with columns like symbol, asof, close",
            type=["csv"],
            accept_multiple_files=False,
        )

        from modules.forex.forex_service import get_forex_service

        service = service or get_forex_service(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            portfolio_id=portfolio_id,
        )

        history_service = service.get_history_service()

        if use_db_latest:

            result = engine.load_latest(limit=200)

        else:

            market_data = history_service.get_market_data(
                source=data_source,
                pairs=selected_pairs,
                uploaded_file=uploaded,
                interval=selected_interval,
                backfill_days=365 * 3,
            )

            result = engine.run_factor_models(
                market_data=market_data,
                pairs=selected_pairs,
                persist=persist,
            )




    result: Dict[str, Any]


    snapshot = result.get("snapshot")
    exposures = result.get("exposures") or []
    signals = result.get("signals") or []
    data_status = result.get("data_status")

    st.caption(f"Data status: {data_status}")
    _render_snapshot(snapshot)

    view = st.radio(
        "Factor Workspace",
        ["Exposures", "Signals", "Factor Weights", "Raw Snapshot"],
        horizontal=True,
    )

    if view == "Exposures":
        if exposures:
            df = pd.DataFrame(exposures)
            preferred = [
                "factor_rank", "symbol", "factor_signal", "factor_conviction", "composite_factor_score",
                "momentum_score", "carry_score", "value_score", "volatility_quality_score",
                "trend_score", "liquidity_score", "macro_score", "close", "volatility_20d", "rationale",
            ]
            cols = [c for c in preferred if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No factor exposures available. Provide price history or load a saved snapshot.")
    elif view == "Signals":
        if signals:
            df = pd.DataFrame(signals)
            preferred = ["symbol", "side", "conviction", "composite_factor_score", "suggested_weight", "risk_bucket", "rationale"]
            cols = [c for c in preferred if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True)
        else:
            st.info("No actionable factor signals were generated from the current input set.")
    elif view == "Factor Weights":
        _render_factor_weights()
    else:
        st.json(snapshot or {})

    return result


__all__ = ["render_forex_factor_models_dashboard"]
