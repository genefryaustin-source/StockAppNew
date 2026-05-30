from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Callable
from datetime import UTC
from sqlalchemy.orm import Session

from modules.analytics.models import AnalyticsSnapshot
from modules.analytics.runner import (
    run_full_analytics,
    run_vectorized_price_analytics,
)
from modules.utils.datetime_utils import (
    to_aware_utc,
)
from modules.universe.service import list_symbols
from modules.market_data.price_cache import warm_price_cache


ProgressFn = Optional[Callable[[int, int, str], None]]


def refresh_universe_cache(
    db: Session,
    tenant_id: str,
    symbols: Optional[List[str]] = None,
    universe_id: Optional[str] = None,
    max_age_hours: int = 72,
    batch_size: int = 25,
    parallel: bool = True,
    max_workers: int = 12,
    progress: ProgressFn = None,
    **kwargs,
):

    if symbols is None and universe_id is not None:
        symbols = list_symbols(db, tenant_id, universe_id)

    if not symbols:
        return {
            "symbols": 0,
            "ran_analytics": 0,
            "parallel": parallel,
            "max_workers": max_workers,
            "batch_size": batch_size,
            "stale_or_missing": 0,
        }

    symbols = [s.strip().upper() for s in symbols if s and s.strip()]
    total_symbols = len(symbols)
    from modules.utils.symbol_classifier import (
        filter_supported_equities,
    )

    symbols = filter_supported_equities(
        symbols
    )
    # warm cache from local DB / table


    print("⚠️ warm_price_cache TEMP DISABLED")



    cutoff = datetime.now(UTC) - timedelta(
        hours=max_age_hours
    )

    rows = (
        db.query(AnalyticsSnapshot.symbol, AnalyticsSnapshot.asof)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol.in_(symbols),
        )
        .all()
    )

    latest: dict[str, datetime] = {}
    for row in rows:
        sym = row.symbol
        asof = row.asof
        if sym not in latest or (latest[sym] is None or (asof is not None and asof > latest[sym])):
            latest[sym] = asof

    to_refresh: List[str] = []

    for s in symbols:
        if s not in latest:
            to_refresh.append(s)
            continue

        asof = latest[s]

        asof_utc = to_aware_utc(asof)

        if (
                asof_utc is None
                or asof_utc < cutoff
        ):
            to_refresh.append(s)

    if not to_refresh:
        return {
            "symbols": total_symbols,
            "ran_analytics": 0,
            "parallel": parallel,
            "max_workers": max_workers,
            "batch_size": batch_size,
            "stale_or_missing": 0,
        }

    # --------------------------------------------
    # FAST PATH: vectorized price-based analytics
    # --------------------------------------------
    ran_fast = run_vectorized_price_analytics(db, tenant_id, to_refresh)

    # progress for the fast path
    if progress:
        done = 0
        total = len(to_refresh)
        for sym in to_refresh:
            done += 1
            progress(done, total, sym)

    # --------------------------------------------
    # OPTIONAL SLOW PATH:
    # only run full analytics for symbols that still
    # need sector / fundamentals enrichment
    # --------------------------------------------
    rows_after = (
        db.query(AnalyticsSnapshot)
        .filter(
            AnalyticsSnapshot.tenant_id == tenant_id,
            AnalyticsSnapshot.symbol.in_(to_refresh),
        )
        .all()
    )

    need_full = []

    for row in rows_after:
        if row.sector in (None, "", "Unknown") or row.revenue_cagr is None:
            need_full.append(row.symbol)

    # de-dup
    need_full = sorted(set(need_full))

    ran_full = 0
    for sym in need_full:
        snap = run_full_analytics(db, tenant_id, sym)
        if snap is not None:
            ran_full += 1

    return {
        "symbols": total_symbols,
        "ran_analytics": ran_fast,
        "ran_full_enrichment": ran_full,
        "parallel": parallel,
        "max_workers": max_workers,
        "batch_size": batch_size,
        "stale_or_missing": len(to_refresh),
    }