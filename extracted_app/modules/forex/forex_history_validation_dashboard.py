"""
modules/forex/forex_history_validation_dashboard.py

Sprint 25 Phase 4.5B-3

Institutional Forex history validation dashboard.

Validates:
- Provider router diagnostics
- History cache stats
- Postgres coverage
- Manual refresh
- Historical data loading
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None


DEFAULT_VALIDATION_PAIRS = [
    "EUR/USD",
    "GBP/USD",
    "USD/JPY",
    "USD/CHF",
    "AUD/USD",
    "NZD/USD",
    "USD/CAD",
    "EUR/GBP",
    "EUR/JPY",
    "GBP/JPY",
]


def _context_value(name: str, default: Optional[str] = None) -> Optional[str]:
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


def _render_table(rows, empty_message: str):
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(empty_message)


def render_forex_history_validation_dashboard(
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

    tenant_id = str(tenant_id or _context_value("tenant_id") or "default")
    user_id = str(user_id or _context_value("user_id") or "") or None
    portfolio_id = str(portfolio_id or _context_value("portfolio_id") or "") or None

    from modules.forex.forex_service import get_forex_service
    from modules.forex.forex_history_refresh_engine import ForexHistoryRefreshEngine

    service = service or get_forex_service(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )

    history_service = service.get_history_service()

    refresh_engine = ForexHistoryRefreshEngine(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        service=history_service,
    )

    st.subheader("Forex History Validation Center")
    st.caption("Sprint 25 Phase 4.5B — provider history, cache, refresh, and PostgreSQL validation.")

    ready = refresh_engine.ensure_ready()

    if ready.get("status") == "READY":
        st.success(ready.get("message"))
    else:
        st.error(ready.get("message"))
        st.caption(ready.get("error"))

    with st.expander("Validation Controls", expanded=True):
        selected_pairs = st.multiselect(
            "Validation Pair Universe",
            options=DEFAULT_VALIDATION_PAIRS,
            default=DEFAULT_VALIDATION_PAIRS[:5],
        )

        interval = st.selectbox(
            "History Interval",
            ["1day", "1hour", "30min", "15min", "5min", "1min"],
            index=0,
        )

        stale_after_hours = st.number_input(
            "Stale After Hours",
            min_value=1,
            max_value=720,
            value=24,
            step=1,
        )

        backfill_days = st.number_input(
            "Backfill Days",
            min_value=30,
            max_value=3650,
            value=365 * 3,
            step=30,
        )

        col1, col2 = st.columns(2)

        run_stale = col1.button(
            "Refresh Stale History",
            key="forex_history_validation_refresh_stale",
        )

        force_refresh = col2.button(
            "Force Refresh History",
            key="forex_history_validation_force_refresh",
        )

    result = {}

    if run_stale:
        with st.spinner("Refreshing stale Forex history..."):
            result = refresh_engine.refresh_if_stale(
                selected_pairs,
                interval=interval,
                stale_after_hours=int(stale_after_hours),
                backfill_days=int(backfill_days),
            )

    if force_refresh:
        with st.spinner("Force refreshing Forex history..."):
            result = refresh_engine.force_refresh(
                selected_pairs,
                interval=interval,
                backfill_days=int(backfill_days),
            )

    if result:
        st.subheader("Refresh Result")
        st.json(result)

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Coverage",
            "Provider Diagnostics",
            "History Cache",
            "Sample History",
        ]
    )

    with tab1:
        st.markdown("### PostgreSQL History Coverage")
        try:
            coverage = history_service.coverage()
            _render_table(coverage, "No Forex history coverage rows are available yet.")
        except Exception as exc:
            st.warning(f"Coverage unavailable: {exc}")

    with tab2:
        st.markdown("### Provider Router Diagnostics")
        try:
            router = history_service.router
            if router is not None and hasattr(router, "history_diagnostics"):
                st.json(router.history_diagnostics())
            elif router is not None and hasattr(router, "diagnostics"):
                st.json(router.diagnostics())
            else:
                st.info("Provider router diagnostics are unavailable.")
        except Exception as exc:
            st.warning(f"Provider diagnostics unavailable: {exc}")

    with tab3:
        st.markdown("### History Cache")
        try:
            router = history_service.router
            if router is not None and hasattr(router, "_history_cache"):
                st.json(router._history_cache.stats())
            else:
                from modules.forex.providers.forex_history_cache import get_forex_history_cache
                st.json(get_forex_history_cache().stats())
        except Exception as exc:
            st.warning(f"History cache diagnostics unavailable: {exc}")

    with tab4:
        st.markdown("### Sample Loaded History")
        try:
            df = history_service.load_history(
                selected_pairs,
                interval=interval,
                limit=500,
            )

            if df is not None and not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No sample history rows are available.")
        except Exception as exc:
            st.warning(f"Sample history unavailable: {exc}")

    return {
        "status": "READY",
        "component": "forex_history_validation_dashboard",
        "tenant_id": tenant_id,
        "portfolio_id": portfolio_id,
        "last_result": result,
    }


__all__ = ["render_forex_history_validation_dashboard"]
