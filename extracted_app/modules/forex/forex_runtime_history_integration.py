"""
modules/forex/forex_runtime_history_integration.py

Sprint 25 Phase 4.5B-3

Drop-in helper used by forex_runtime_manager.py or forex_workspace.py to ensure
Forex historical data is refreshed once when the Forex workspace opens.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional


DEFAULT_FOREX_HISTORY_BOOTSTRAP_PAIRS = [
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


def bootstrap_forex_history_on_workspace_open(
    *,
    db: Any = None,
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    portfolio_id: Optional[str] = None,
    pairs: Optional[Iterable[str]] = None,
    interval: str = "1day",
    stale_after_hours: int = 24,
    backfill_days: int = 365 * 3,
) -> dict[str, Any]:
    from modules.forex.forex_history_refresh_engine import ForexHistoryRefreshEngine

    engine = ForexHistoryRefreshEngine(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )

    engine.ensure_ready()

    return engine.refresh_on_workspace_open(
        pairs=list(pairs or DEFAULT_FOREX_HISTORY_BOOTSTRAP_PAIRS),
        interval=interval,
        stale_after_hours=stale_after_hours,
        backfill_days=backfill_days,
    )
