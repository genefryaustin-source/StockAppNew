"""
modules/analytics/universe_aware_analytics_runner.py
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import text


DEFAULT_ANALYTICS_BATCH_SIZE = 250


def get_symbols_for_universe(
    db,
    universe_id: str,
    tenant_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[str]:
    params = {
        "universe_id": universe_id,
    }

    tenant_clause = ""

    if tenant_id:
        tenant_clause = "AND tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id

    limit_clause = ""

    if limit:
        limit_clause = "LIMIT :limit"
        params["limit"] = int(limit)

    rows = db.execute(text(f"""
        SELECT DISTINCT symbol
        FROM universe_symbols
        WHERE universe_id = :universe_id
        {tenant_clause}
        ORDER BY symbol
        {limit_clause}
    """), params).fetchall()

    return [
        str(r[0]).upper().strip()
        for r in rows
        if r[0]
    ]


def run_universe_aware_analytics(
    db,
    tenant_id: str,
    universe_id: str,
    max_symbols: int = DEFAULT_ANALYTICS_BATCH_SIZE,
) -> Dict[str, Any]:
    from modules.analytics.incremental_runner import run_incremental_analytics

    symbols = get_symbols_for_universe(
        db=db,
        universe_id=universe_id,
        tenant_id=tenant_id,
        limit=max_symbols,
    )

    if not symbols:
        return {
            "universe_id": universe_id,
            "tenant_id": tenant_id,
            "symbols": 0,
            "processed": 0,
            "failed": 0,
        }

    result = run_incremental_analytics(
        db,
        tenant_id,
        symbols,
    )

    return {
        "universe_id": universe_id,
        "tenant_id": tenant_id,
        "symbols": len(symbols),
        "processed": int(result.get("processed", 0)),
        "failed": int(result.get("failed", 0)),
    }


def get_universe_analytics_summary(
    db,
    tenant_id: str,
    universe_id: str,
) -> Dict[str, Any]:
    total_symbols = db.execute(text("""
        SELECT COUNT(DISTINCT symbol)
        FROM universe_symbols
        WHERE universe_id = :universe_id
        AND tenant_id = :tenant_id
    """), {
        "universe_id": universe_id,
        "tenant_id": tenant_id,
    }).scalar() or 0

    analyzed_symbols = db.execute(text("""
        SELECT COUNT(DISTINCT symbol)
        FROM analytics_snapshots
        WHERE tenant_id = :tenant_id
        AND symbol IN (
            SELECT DISTINCT symbol
            FROM universe_symbols
            WHERE universe_id = :universe_id
            AND tenant_id = :tenant_id
        )
    """), {
        "universe_id": universe_id,
        "tenant_id": tenant_id,
    }).scalar() or 0

    return {
        "universe_id": universe_id,
        "tenant_id": tenant_id,
        "total_symbols": int(total_symbols),
        "analyzed_symbols": int(analyzed_symbols),
        "missing_analytics": max(
            0,
            int(total_symbols) - int(analyzed_symbols),
        ),
    }