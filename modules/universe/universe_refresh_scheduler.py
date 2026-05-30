"""
modules/universe/universe_refresh_scheduler.py

Universe auto-refresh scheduler.

Uses:
- universes
- universe_symbols

Purpose:
- Detect universes due for refresh
- Enqueue refresh jobs every N hours
- Avoid duplicate active jobs
- Track last/next refresh
- Refresh symbols in safe batches
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd
from sqlalchemy import text


DEFAULT_REFRESH_INTERVAL_HOURS = 72
DEFAULT_MAX_SYMBOLS_PER_RUN = 250
DEFAULT_BATCH_SIZE = 50


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_universe_refresh_tables(db) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS universe_refresh_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            universe_id TEXT NOT NULL,
            universe_name TEXT,
            status TEXT DEFAULT 'PENDING',
            refresh_interval_hours INTEGER DEFAULT 72,
            last_refresh DATETIME,
            next_refresh DATETIME,
            symbols_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_universe_refresh_jobs_status
        ON universe_refresh_jobs(status)
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_universe_refresh_jobs_next_refresh
        ON universe_refresh_jobs(next_refresh)
    """))

    db.commit()


def get_universes_with_symbols(db) -> List[Dict[str, Any]]:
    rows = db.execute(text("""
        SELECT
            u.id AS universe_id,
            u.name AS universe_name,
            COUNT(DISTINCT us.symbol) AS symbols_count
        FROM universes u
        JOIN universe_symbols us
            ON us.universe_id = u.id
        GROUP BY
            u.id,
            u.name
        HAVING COUNT(DISTINCT us.symbol) > 0
        ORDER BY u.name
    """)).fetchall()

    return [
        {
            "universe_id": str(r.universe_id),
            "universe_name": r.universe_name,
            "symbols_count": int(r.symbols_count or 0),
        }
        for r in rows
    ]


def get_latest_refresh_job(db, universe_id: str):
    return db.execute(text("""
        SELECT *
        FROM universe_refresh_jobs
        WHERE universe_id = :universe_id
        ORDER BY created_at DESC
        LIMIT 1
    """), {
        "universe_id": universe_id,
    }).fetchone()


def has_active_refresh_job(db, universe_id: str) -> bool:
    row = db.execute(text("""
        SELECT id
        FROM universe_refresh_jobs
        WHERE universe_id = :universe_id
        AND status IN ('PENDING', 'RUNNING')
        LIMIT 1
    """), {
        "universe_id": universe_id,
    }).fetchone()

    return row is not None


def seed_missing_universe_refresh_jobs(
    db,
    refresh_interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
) -> int:
    ensure_universe_refresh_tables(db)

    created = 0
    now = utc_now()

    for universe in get_universes_with_symbols(db):
        universe_id = universe["universe_id"]

        if get_latest_refresh_job(db, universe_id):
            continue

        db.execute(text("""
            INSERT INTO universe_refresh_jobs (
                universe_id,
                universe_name,
                status,
                refresh_interval_hours,
                last_refresh,
                next_refresh,
                symbols_count,
                updated_at
            )
            VALUES (
                :universe_id,
                :universe_name,
                'PENDING',
                :refresh_interval_hours,
                NULL,
                :next_refresh,
                :symbols_count,
                :updated_at
            )
        """), {
            "universe_id": universe_id,
            "universe_name": universe["universe_name"],
            "refresh_interval_hours": int(refresh_interval_hours),
            "next_refresh": now,
            "symbols_count": universe["symbols_count"],
            "updated_at": now,
        })

        created += 1

    db.commit()
    return created


def enqueue_due_universe_refresh_jobs(
    db,
    refresh_interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
) -> int:
    ensure_universe_refresh_tables(db)
    seed_missing_universe_refresh_jobs(
        db,
        refresh_interval_hours=refresh_interval_hours,
    )

    now = utc_now()
    enqueued = 0

    for universe in get_universes_with_symbols(db):
        universe_id = universe["universe_id"]

        if has_active_refresh_job(db, universe_id):
            continue

        latest = get_latest_refresh_job(db, universe_id)

        if latest is None:
            due = True
        else:
            next_refresh = latest.next_refresh
            due = next_refresh is None or next_refresh <= now

        if not due:
            continue

        db.execute(text("""
            INSERT INTO universe_refresh_jobs (
                universe_id,
                universe_name,
                status,
                refresh_interval_hours,
                last_refresh,
                next_refresh,
                symbols_count,
                updated_at
            )
            VALUES (
                :universe_id,
                :universe_name,
                'PENDING',
                :refresh_interval_hours,
                NULL,
                :next_refresh,
                :symbols_count,
                :updated_at
            )
        """), {
            "universe_id": universe_id,
            "universe_name": universe["universe_name"],
            "refresh_interval_hours": int(refresh_interval_hours),
            "next_refresh": now,
            "symbols_count": universe["symbols_count"],
            "updated_at": now,
        })

        enqueued += 1

    db.commit()
    return enqueued


def get_pending_refresh_jobs(db, limit: int = 1):
    ensure_universe_refresh_tables(db)

    return db.execute(text("""
        SELECT *
        FROM universe_refresh_jobs
        WHERE status = 'PENDING'
        ORDER BY next_refresh ASC, created_at ASC
        LIMIT :limit
    """), {
        "limit": int(limit),
    }).fetchall()


def get_symbols_for_universe(
    db,
    universe_id: str,
) -> List[str]:
    rows = db.execute(text("""
        SELECT DISTINCT symbol
        FROM universe_symbols
        WHERE universe_id = :universe_id
        ORDER BY symbol
    """), {
        "universe_id": universe_id,
    }).fetchall()

    return [
        str(r[0]).upper().strip()
        for r in rows
        if r[0]
    ]


def mark_job_running(db, job_id: int) -> None:
    db.execute(text("""
        UPDATE universe_refresh_jobs
        SET status = 'RUNNING',
            updated_at = :updated_at
        WHERE id = :job_id
    """), {
        "job_id": int(job_id),
        "updated_at": utc_now(),
    })
    db.commit()


def mark_job_complete(
    db,
    job_id: int,
    refresh_interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
) -> None:
    now = utc_now()
    next_refresh = now + timedelta(hours=int(refresh_interval_hours))

    db.execute(text("""
        UPDATE universe_refresh_jobs
        SET status = 'COMPLETED',
            last_refresh = :last_refresh,
            next_refresh = :next_refresh,
            updated_at = :updated_at
        WHERE id = :job_id
    """), {
        "job_id": int(job_id),
        "last_refresh": now,
        "next_refresh": next_refresh,
        "updated_at": now,
    })
    db.commit()


def mark_job_failed(
    db,
    job_id: int,
    reason: str = "",
    retry_hours: int = 6,
) -> None:
    now = utc_now()
    retry_at = now + timedelta(hours=int(retry_hours))

    db.execute(text("""
        UPDATE universe_refresh_jobs
        SET status = 'FAILED',
            next_refresh = :next_refresh,
            updated_at = :updated_at
        WHERE id = :job_id
    """), {
        "job_id": int(job_id),
        "next_refresh": retry_at,
        "updated_at": now,
    })

    db.commit()

    if reason:
        print(f"Universe refresh job {job_id} failed: {reason}")


def _chunks(items: List[str], size: int) -> List[List[str]]:
    return [
        items[i:i + size]
        for i in range(0, len(items), size)
    ]


def run_due_universe_refresh_jobs(
    db,
    user: Optional[Dict[str, Any]] = None,
    max_jobs: int = 1,
    refresh_interval_hours: int = DEFAULT_REFRESH_INTERVAL_HOURS,
    max_symbols_per_run: int = DEFAULT_MAX_SYMBOLS_PER_RUN,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> Dict[str, Any]:
    from modules.market_data.updater import update_latest_prices
    from modules.analytics.incremental_runner import run_incremental_analytics

    ensure_universe_refresh_tables(db)

    enqueue_due_universe_refresh_jobs(
        db,
        refresh_interval_hours=refresh_interval_hours,
    )

    jobs = get_pending_refresh_jobs(db, limit=max_jobs)

    result = {
        "jobs_found": len(jobs),
        "jobs_completed": 0,
        "jobs_failed": 0,
        "symbols_refreshed": 0,
        "analytics_processed": 0,
        "details": [],
    }

    tenant_id = user.get("tenant_id") if isinstance(user, dict) else None

    for job in jobs:
        job_id = int(job.id)

        try:
            mark_job_running(db, job_id)

            all_symbols = get_symbols_for_universe(
                db,
                str(job.universe_id),
            )

            selected_symbols = all_symbols[: int(max_symbols_per_run)]

            if not selected_symbols:
                mark_job_complete(
                    db,
                    job_id,
                    refresh_interval_hours=refresh_interval_hours,
                )
                continue

            updated_symbols: List[str] = []
            total_updated = 0
            total_skipped = 0
            total_failed = 0

            for batch in _chunks(
                selected_symbols,
                int(batch_size),
            ):
                refresh_result = update_latest_prices(
                    db,
                    batch,
                )

                batch_updated = refresh_result.get(
                    "updated_symbols",
                    [],
                )

                updated_symbols.extend(batch_updated)
                total_updated += int(refresh_result.get("updated", 0))
                total_skipped += int(refresh_result.get("skipped", 0))
                total_failed += int(refresh_result.get("failed", 0))

            analytics_result = {
                "processed": 0,
                "failed": 0,
            }

            if updated_symbols and tenant_id:
                analytics_result = run_incremental_analytics(
                    db,
                    tenant_id,
                    list(dict.fromkeys(updated_symbols)),
                )

            mark_job_complete(
                db,
                job_id,
                refresh_interval_hours=refresh_interval_hours,
            )

            result["jobs_completed"] += 1
            result["symbols_refreshed"] += len(set(updated_symbols))
            result["analytics_processed"] += int(
                analytics_result.get("processed", 0)
            )

            result["details"].append({
                "job_id": job_id,
                "universe_id": str(job.universe_id),
                "universe_name": job.universe_name,
                "symbols_available": len(all_symbols),
                "symbols_attempted": len(selected_symbols),
                "updated": total_updated,
                "skipped": total_skipped,
                "failed": total_failed,
                "analytics_processed": analytics_result.get("processed", 0),
                "analytics_failed": analytics_result.get("failed", 0),
            })

        except Exception as e:
            mark_job_failed(
                db,
                job_id,
                reason=str(e),
            )

            result["jobs_failed"] += 1
            result["details"].append({
                "job_id": job_id,
                "universe_id": str(job.universe_id),
                "universe_name": job.universe_name,
                "error": str(e),
            })

    return result


def get_refresh_job_status(db, limit: int = 50) -> pd.DataFrame:
    ensure_universe_refresh_tables(db)

    rows = db.execute(text("""
        SELECT
            id,
            universe_id,
            universe_name,
            status,
            symbols_count,
            refresh_interval_hours,
            last_refresh,
            next_refresh,
            created_at,
            updated_at
        FROM universe_refresh_jobs
        ORDER BY created_at DESC
        LIMIT :limit
    """), {
        "limit": int(limit),
    }).fetchall()

    return pd.DataFrame([
        dict(r._mapping)
        for r in rows
    ])