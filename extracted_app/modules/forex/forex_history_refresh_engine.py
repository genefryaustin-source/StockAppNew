"""
modules/forex/forex_history_refresh_engine.py

Sprint 25 Phase 4.5B-3

Runtime refresh engine for Forex historical market data.

Responsibilities:
- Ensure Postgres history tables exist
- Detect stale historical data
- Refresh missing/stale history through ForexHistoryService
- Preserve tenant_id/user_id/portfolio_id context
- Return dashboard-friendly refresh diagnostics
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional


DEFAULT_HISTORY_PAIRS = [
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
    "AUD/JPY",
    "CAD/JPY",
]


class ForexHistoryRefreshEngine:
    def __init__(
        self,
        db: Any = None,
        *,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        portfolio_id: Optional[str] = None,
        service: Any = None,
    ):
        self.db = db
        self.tenant_id = tenant_id or "default"
        self.user_id = user_id
        self.portfolio_id = portfolio_id

        if service is None:
            from modules.forex.forex_history_service import ForexHistoryService

            service = ForexHistoryService(
                db=db,
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                portfolio_id=self.portfolio_id,
            )

        self.service = service

    @staticmethod
    def _now_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def ensure_ready(self) -> dict[str, Any]:
        try:
            self.service.ensure_tables()
            return {
                "status": "READY",
                "message": "Forex history tables are ready.",
            }
        except Exception as exc:
            return {
                "status": "ERROR",
                "message": "Failed to ensure Forex history tables.",
                "error": str(exc),
            }

    def refresh_if_stale(
        self,
        pairs: Iterable[str],
        *,
        interval: str = "1day",
        stale_after_hours: int = 24,
        backfill_days: int = 365 * 3,
    ) -> dict[str, Any]:
        self.service.ensure_tables()

        result = self.service.ensure_fresh_history(
            pairs=pairs,
            interval=interval,
            stale_after_hours=stale_after_hours,
            backfill_days=backfill_days,
        )

        result["component"] = "ForexHistoryRefreshEngine"
        result["tenant_id"] = self.tenant_id
        result["portfolio_id"] = self.portfolio_id
        result["interval"] = interval
        result["generated_at"] = self._now_naive().isoformat()

        return result

    def refresh_on_workspace_open(
        self,
        *,
        pairs: Optional[Iterable[str]] = None,
        interval: str = "1day",
        stale_after_hours: int = 24,
        backfill_days: int = 365 * 3,
        session_key: str = "forex_history_refresh_completed",
    ) -> dict[str, Any]:
        selected_pairs = list(pairs or DEFAULT_HISTORY_PAIRS)

        # Streamlit-safe one-run-per-session guard. If Streamlit is unavailable,
        # this simply refreshes according to stale detection.
        try:
            import streamlit as st

            tenant_key = f"{session_key}:{self.tenant_id}:{self.portfolio_id}:{interval}"

            if st.session_state.get(tenant_key):
                return {
                    "status": "SKIPPED",
                    "reason": "already_refreshed_this_session",
                    "pairs": len(selected_pairs),
                    "interval": interval,
                }

            result = self.refresh_if_stale(
                selected_pairs,
                interval=interval,
                stale_after_hours=stale_after_hours,
                backfill_days=backfill_days,
            )

            st.session_state[tenant_key] = True

            return result

        except Exception:
            return self.refresh_if_stale(
                selected_pairs,
                interval=interval,
                stale_after_hours=stale_after_hours,
                backfill_days=backfill_days,
            )

    def force_refresh(
        self,
        pairs: Iterable[str],
        *,
        interval: str = "1day",
        backfill_days: int = 365 * 3,
    ) -> dict[str, Any]:
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=int(backfill_days))

        return self.service.refresh_universe(
            pairs,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            force_refresh=True,
        )


def get_forex_history_refresh_engine(
    db: Any = None,
    *,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    service: Any = None,
) -> ForexHistoryRefreshEngine:
    return ForexHistoryRefreshEngine(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
        service=service,
    )
