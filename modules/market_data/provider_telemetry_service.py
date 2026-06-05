"""
modules/market_data/provider_telemetry_service.py
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Dict, Any, List

from sqlalchemy import text

from modules.market_data.provider_router import (
    get_provider_router,
)

from modules.market_data.adaptive_rate_limit_manager import (
    get_rate_limit_manager,
)


def ensure_provider_telemetry_tables(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS provider_telemetry (
            id INTEGER PRIMARY KEY,
            provider TEXT NOT NULL,
            health_score REAL,
            success_count INTEGER,
            failure_count INTEGER,
            rate_limit_count INTEGER,
            avg_latency_ms REAL,
            requests_today INTEGER,
            cooldown_until DATETIME,
            captured_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS
        ix_provider_telemetry_provider
        ON provider_telemetry(provider)
    """))

    db.commit()


def capture_provider_snapshot(db):
    ensure_provider_telemetry_tables(db)

    router = get_provider_router()

    for provider in router.all_providers():

        db.execute(text("""
            INSERT INTO provider_telemetry (
                provider,
                health_score,
                success_count,
                failure_count,
                rate_limit_count,
                avg_latency_ms,
                requests_today,
                cooldown_until,
                captured_at
            )
            VALUES (
                :provider,
                :health_score,
                :success_count,
                :failure_count,
                :rate_limit_count,
                :avg_latency_ms,
                :requests_today,
                :cooldown_until,
                :captured_at
            )
        """), {
            "provider": provider.provider,
            "health_score": provider.health_score,
            "success_count": provider.success_count,
            "failure_count": provider.failure_count,
            "rate_limit_count": provider.rate_limit_count,
            "avg_latency_ms": provider.avg_latency_ms,
            "requests_today": provider.requests_today,
            "cooldown_until": provider.cooldown_until,
            "captured_at": datetime.now(UTC),
        })

    db.commit()


def get_provider_telemetry_history(
    db,
    provider: str | None = None,
    limit: int = 500,
) -> List[Dict[str, Any]]:

    ensure_provider_telemetry_tables(db)

    if provider:

        rows = db.execute(text("""
            SELECT *
            FROM provider_telemetry
            WHERE provider = :provider
            ORDER BY captured_at DESC
            LIMIT :limit
        """), {
            "provider": provider.upper(),
            "limit": limit,
        }).fetchall()

    else:

        rows = db.execute(text("""
            SELECT *
            FROM provider_telemetry
            ORDER BY captured_at DESC
            LIMIT :limit
        """), {
            "limit": limit,
        }).fetchall()

    return [
        dict(r._mapping)
        for r in rows
    ]


def get_provider_telemetry_summary(db):

    ensure_provider_telemetry_tables(db)

    rows = db.execute(text("""
        SELECT
            provider,
            MAX(captured_at) AS latest_capture,
            MAX(health_score) AS health_score,
            MAX(success_count) AS success_count,
            MAX(failure_count) AS failure_count,
            MAX(rate_limit_count) AS rate_limit_count
        FROM provider_telemetry
        GROUP BY provider
        ORDER BY provider
    """)).fetchall()

    return [
        dict(r._mapping)
        for r in rows
    ]