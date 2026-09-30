"""
modules/universe/shared_refresh.py

Propagates a fresh universe_refresh analytics run to every other tenant
that maintains its own copy of the same "shared" market universe (NYSE,
NASDAQ, S&P 500, AMEX today -- see SHARED_UNIVERSE_NAMES). These are
conceptually identical across tenants (same real symbols, same public
market data) even though each tenant currently owns its own separate
Universe/UniverseSymbol rows with a different universe_id -- there is
no schema-level link between "NYSE for Tenant A" and "NYSE for Tenant
B" today.

Without this, refreshing "NYSE" for one tenant does nothing for any
other tenant's own "NYSE" copy, forcing a full independent (and
identically expensive -- same live Finnhub/FMP/Alpha Vantage/price
provider calls) analytics run per tenant for data that is, and should
be, the same everywhere. This makes one tenant's successful refresh
also refresh every other tenant sharing that universe, via a plain DB
copy of the already-computed analytics_snapshots rows -- no additional
provider calls.

Restricted to an explicit name allow-list rather than "any universe
sharing a name" so that two tenants who happen to create their own
identically-named custom watchlist don't silently start mirroring each
other's analytics.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from modules.db.models import gen_uuid
from modules.universe.models import Universe, UniverseSymbol
from modules.analytics.models import AnalyticsSnapshot


SHARED_UNIVERSE_NAMES = {"nyse", "nasdaq", "s&p 500", "amex"}


# Every AnalyticsSnapshot column that should be mirrored verbatim from
# the source tenant's fresh row to each target tenant's row. Deliberately
# excludes id/tenant_id/symbol, which each target row keeps (or is given)
# its own value for.
_COPY_COLUMNS = [
    "asof", "sector",
    "gross_margin", "operating_margin", "fcf_margin", "revenue_cagr",
    "pe_ttm", "ps_ttm", "ev_ebitda",
    "trend", "rsi_14", "sma_50", "sma_200", "support", "resistance",
    "vol_20d", "max_drawdown_1y", "risk_score",
    "rating", "rating_rationale",
    "quality_score", "growth_score", "value_score", "momentum_score",
    "composite_score", "confidence_score", "latest_volume",
    "signal", "signal_rationale", "sentiment_score",
]


def is_shared_universe_name(name: Optional[str]) -> bool:
    return bool(name) and name.strip().lower() in SHARED_UNIVERSE_NAMES


def propagate_shared_universe_analytics(
    db: Session,
    source_tenant_id: str,
    source_universe_id: str,
) -> dict[str, Any]:
    """
    Call this right after a universe_refresh job succeeds for
    (source_tenant_id, source_universe_id). If that universe's name is
    on the shared allow-list, every other tenant with a universe of the
    same name (case-insensitive) gets its own analytics_snapshots rows
    upserted with the source tenant's just-refreshed values, for every
    symbol both tenants' copies have in common.

    Safe to call unconditionally after every universe_refresh job --
    it's a no-op (skipped=True) for any universe not on the allow-list.
    """
    source_universe = (
        db.query(Universe)
        .filter(
            Universe.id == source_universe_id,
            Universe.tenant_id == source_tenant_id,
        )
        .first()
    )

    if source_universe is None or not is_shared_universe_name(source_universe.name):
        return {
            "skipped": True,
            "reason": "not a shared universe",
            "propagated_tenants": 0,
            "symbols_copied": 0,
        }

    name_lower = source_universe.name.strip().lower()

    target_universes = (
        db.query(Universe)
        .filter(
            func.lower(Universe.name) == name_lower,
            Universe.tenant_id != source_tenant_id,
        )
        .all()
    )

    if not target_universes:
        return {"propagated_tenants": 0, "symbols_copied": 0}

    source_snapshots = {
        s.symbol: s
        for s in db.query(AnalyticsSnapshot)
        .filter(AnalyticsSnapshot.tenant_id == source_tenant_id)
        .all()
    }

    propagated_tenants = 0
    symbols_copied = 0

    for target_universe in target_universes:
        target_tenant_id = target_universe.tenant_id

        target_symbols = {
            row.symbol
            for row in db.query(UniverseSymbol.symbol)
            .filter(
                UniverseSymbol.tenant_id == target_tenant_id,
                UniverseSymbol.universe_id == target_universe.id,
            )
            .all()
        }

        matched = target_symbols & source_snapshots.keys()

        if not matched:
            continue

        existing_target = {
            s.symbol: s
            for s in db.query(AnalyticsSnapshot)
            .filter(
                AnalyticsSnapshot.tenant_id == target_tenant_id,
                AnalyticsSnapshot.symbol.in_(matched),
            )
            .all()
        }

        for sym in matched:
            src = source_snapshots[sym]
            dst = existing_target.get(sym)

            if dst is None:
                dst = AnalyticsSnapshot(
                    id=gen_uuid(),
                    tenant_id=target_tenant_id,
                    symbol=sym,
                )
                db.add(dst)

            for col in _COPY_COLUMNS:
                setattr(dst, col, getattr(src, col))

        propagated_tenants += 1
        symbols_copied += len(matched)

    db.commit()

    return {
        "propagated_tenants": propagated_tenants,
        "symbols_copied": symbols_copied,
    }