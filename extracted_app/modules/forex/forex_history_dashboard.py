"""
modules/forex/forex_history_dashboard.py

Sprint 25 Phase 4.5 - Historical Market Data Platform Dashboard

Admin/operator view for Forex historical price coverage, provider refresh, and Postgres validation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from modules.forex.forex_history_refresh_engine import ForexHistoryRefreshEngine
from modules.forex.forex_history_service import ForexHistoryService

try:
    from modules.forex.forex_service import SUPPORTED_PAIRS
except Exception:
    SUPPORTED_PAIRS = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD"]


def _get_context_value(name: str, default: Optional[str] = None) -> Optional[str]:
    if st is None:
        return default
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


def render_forex_history_dashboard(
    *,
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    service: Any = None,
    runtime: Any = None,
    **kwargs: Any,
) -> dict[str, Any]:
    if st is None:
        return {"status": "streamlit_not_available"}

    tenant_id = str(tenant_id or _get_context_value("tenant_id") or "default")
    user_id = str(user_id or _get_context_value("user_id") or "") or None
    portfolio_id = str(portfolio_id or _get_context_value("portfolio_id") or "") or None

    st.subheader("Forex Historical Market Data")
    st.caption("Sprint 25 Phase 4.5 — shared Postgres-backed historical OHLCV data for all Forex analytics.")

    from modules.forex.forex_service import get_forex_service

    service = service or get_forex_service(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )

    history_service = service.get_history_service()

    refresh_engine = service.get_history_refresh_engine()

    if db is None:
        st.warning("No database session was supplied. Provider refresh can be tested, but Postgres persistence is disabled.")
    else:
        try:
            history_service.ensure_tables()
            st.success("Forex history tables are ready.")
        except Exception as exc:
            st.error(f"Failed to initialize Forex history tables: {exc}")

    with st.expander("History Operations", expanded=True):

        col1, col2, col3 = st.columns(3)

        with col1:
            selected_pairs = st.multiselect(
                "History Universe",
                options=list(SUPPORTED_PAIRS),
                default=list(SUPPORTED_PAIRS[:6]),
            )

        with col2:
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

            backfill_days = st.number_input(
                "Backfill Days",
                min_value=5,
                max_value=3650,
                value=365 * 3,
                step=30,
            )

        with col3:
            stale_after_hours = st.number_input(
                "Refresh If Older Than Hours",
                min_value=1,
                max_value=168,
                value=24,
                step=1,
            )

            history_action = st.radio(
                "History Action",
                [
                    "View History",
                    "Refresh Stale",
                    "Force Refresh",
                    "Coverage Report",
                    "Provider Diagnostics",
                ],
                horizontal=False,
            )

        run_action = st.button(
            "Run History Action",
            type="primary",
            use_container_width=True,
        )

    result: dict[str, Any] = {"status": "idle"}

    coverage = None
    sample = None
    diagnostics = None

    if run_action:

        if history_action == "View History":

            sample = history_service.load_history(
                pairs=selected_pairs,
                interval=selected_interval,
                limit=500,
            )

        elif history_action == "Refresh Stale":

            result = history_service.ensure_fresh_history(
                pairs=selected_pairs,
                interval=selected_interval,
                stale_after_hours=int(stale_after_hours),
                backfill_days=int(backfill_days),
            )

            st.success(
                f"Refresh complete. Rows inserted: {result.get('rows_inserted', 0):,}"
            )

            with st.expander("Refresh Result", expanded=False):
                st.json(result)

        elif history_action == "Force Refresh":

            result = refresh_engine.force_refresh(
                pairs=selected_pairs,
                interval=selected_interval,
                backfill_days=int(backfill_days),
            )

            st.success(
                f"Force refresh complete. Rows inserted: {result.get('rows_inserted', 0):,}"
            )

            with st.expander("Refresh Result", expanded=False):
                st.json(result)

        elif history_action == "Coverage Report":

            coverage = history_service.coverage()

        elif history_action == "Provider Diagnostics":

            router = history_service.router

            if router is not None and hasattr(router, "history_diagnostics"):
                diagnostics = router.history_diagnostics()
            elif router is not None and hasattr(router, "diagnostics"):
                diagnostics = router.diagnostics()
        st.success(f"Refresh complete. Rows inserted/updated: {result.get('rows_inserted', 0):,}")
        with st.expander("Refresh Result", expanded=False):
            st.json(result)


    st.divider()

    # ==========================================================
    # PostgreSQL Coverage
    # ==========================================================
    st.markdown("### PostgreSQL Coverage")

    try:

        if coverage is None:
            coverage = history_service.coverage()

        if coverage:
            st.dataframe(
                pd.DataFrame(coverage),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info(
                "No persisted Forex history found yet. "
                "Run a refresh or import historical data."
            )

    except Exception as exc:
        st.warning(f"Coverage unavailable: {exc}")

    # ==========================================================
    # Provider Diagnostics
    # ==========================================================
    st.markdown("### Provider Diagnostics")

    try:

        if diagnostics is None:

            router = history_service.router

            if router is not None:

                if hasattr(router, "history_diagnostics"):
                    diagnostics = router.history_diagnostics()

                elif hasattr(router, "diagnostics"):
                    diagnostics = router.diagnostics()

        if diagnostics:
            st.json(diagnostics)
        else:
            st.info("Provider diagnostics are unavailable.")

    except Exception as exc:
        st.warning(f"Diagnostics unavailable: {exc}")

    # ==========================================================
    # Sample History
    # ==========================================================
    st.markdown("### Sample History")

    try:

        if sample is None:
            sample_pairs = selected_pairs or list(SUPPORTED_PAIRS[:3])

            sample = history_service.load_history(
                pairs=sample_pairs,
                interval=selected_interval,
                limit=500,
            )

        if sample is not None and not sample.empty:

            preferred = [
                "pair",
                "symbol",
                "asof",
                "interval",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "provider",
                "source",
            ]

            cols = [c for c in preferred if c in sample.columns]

            st.dataframe(
                sample[cols],
                use_container_width=True,
                hide_index=True,
            )

        else:
            st.info(
                "No sample history available for the selected universe."
            )

    except Exception as exc:
        st.warning(f"Sample history unavailable: {exc}")

    return result




__all__ = ["render_forex_history_dashboard"]
