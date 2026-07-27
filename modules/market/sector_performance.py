"""
modules/market/sector_performance.py

Sector Performance

Real sector-level performance computed from a tenant's own tracked
universe: AnalyticsSnapshot.sector (real classifications already
stored for that tenant's symbols) grouped against real daily returns
from stored price history.

Honesty note: this is NOT a full, market-wide GICS sector breakdown --
it reflects whatever sectors and symbols exist in this tenant's own
analytics_snapshots. A tenant with a narrow or US-tech-heavy universe
will see narrow or tech-heavy sector coverage here, not a guaranteed
11/12-sector market-wide view. This replaces modules.market.
sector_heatmap.py's SECTOR_MAP, which was a hardcoded 6-sector,
2-3-stocks-each stub, not reachable from the live app, and not
representative of any tenant's actual universe.
"""

from __future__ import annotations

from datetime import datetime, UTC

import pandas as pd


def _latest_sector_map(db, tenant_id: str) -> dict[str, str]:
    """symbol -> sector, most recent snapshot per symbol for this tenant."""
    from modules.analytics.snapshot_cache import get_latest_snapshots_df

    df = get_latest_snapshots_df(db, tenant_id)

    if df is None or df.empty or "sector" not in df.columns:
        return {}

    return {
        row["symbol"]: row["sector"]
        for _, row in df.iterrows()
        if row.get("sector")
    }


def _returns_for_symbols(db, symbols: list[str]) -> dict[str, float]:
    """
    1-day % return for every symbol given, computed from ONE query
    (modules.market_data.price_history_service.load_close_matrix)
    instead of one query per symbol.

    This replaces a per-symbol loop that called load_price_history()
    once for every symbol (each fetching that symbol's entire stored
    history, not just the couple of recent days actually needed) --
    confirmed directly, via timing instrumentation, to account for
    ~149 of a ~149.4 second total market dashboard load against a
    remote/cloud (Neon) database, where every separate round-trip
    carries real network latency regardless of how little data it
    returns.
    """
    from modules.market_data.price_history_service import load_close_matrix

    matrix = load_close_matrix(db, symbols)

    if matrix is None or matrix.empty or len(matrix) < 2:
        return {}

    returns: dict[str, float] = {}
    for symbol in matrix.columns:
        closes = matrix[symbol].dropna()
        if len(closes) < 2:
            continue

        prev = float(closes.iloc[-2])
        last = float(closes.iloc[-1])

        if prev == 0:
            continue

        returns[symbol] = (last / prev) - 1.0

    return returns


def get_sector_performance(db, *, tenant_id: str, top_n_per_sector: int = 5) -> dict:
    """
    Real sector-level 1-day performance for this tenant's own tracked
    universe, with the top movers driving each sector's move.
    """
    sector_map = _latest_sector_map(db, tenant_id)

    if not sector_map:
        return {
            "available": False,
            "reason": "No analytics snapshots (with sector classifications) available yet for this tenant.",
        }

    by_symbol_return = _returns_for_symbols(db, list(sector_map.keys()))

    if not by_symbol_return:
        return {
            "available": False,
            "reason": "No stored price history available yet to compute returns.",
        }

    sector_rows: dict[str, list[dict]] = {}
    for symbol, sector in sector_map.items():
        ret = by_symbol_return.get(symbol)
        if ret is None:
            continue
        sector_rows.setdefault(sector, []).append({
            "symbol": symbol,
            "return_pct": round(ret * 100.0, 2),
        })

    sectors = []
    for sector, rows in sector_rows.items():
        avg_return = sum(r["return_pct"] for r in rows) / len(rows)
        top_movers = sorted(rows, key=lambda r: abs(r["return_pct"]), reverse=True)[:top_n_per_sector]

        sectors.append({
            "sector": sector,
            "avg_return_pct": round(avg_return, 2),
            "symbol_count": len(rows),
            "top_movers": top_movers,
        })

    sectors.sort(key=lambda s: s["avg_return_pct"], reverse=True)

    return {
        "as_of": datetime.now(UTC).isoformat(),
        "sector_count": len(sectors),
        "sectors": sectors,
        "coverage_note": (
            "Reflects this tenant's own tracked universe, not a guaranteed "
            "full market-wide GICS sector breakdown."
        ),
    }