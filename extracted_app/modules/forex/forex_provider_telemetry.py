
"""
modules/forex/forex_provider_telemetry.py
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from modules.forex.providers.forex_provider_router import (
    get_forex_provider_router,
)


class ForexProviderTelemetry:

    def __init__(self, db=None):
        self.db = db
        self.router = get_forex_provider_router()

    def ensure_tables(self):
        if self.db is None:
            return

        self.db.execute(text("""
        CREATE TABLE IF NOT EXISTS forex_provider_telemetry(
            id SERIAL PRIMARY KEY,
            provider VARCHAR(100),
            health_score DOUBLE PRECISION,
            success_count INTEGER,
            failure_count INTEGER,
            rate_limit_count INTEGER,
            auth_error_count INTEGER,
            invalid_response_count INTEGER,
            avg_latency_ms DOUBLE PRECISION,
            requests_today INTEGER,
            cooldown_until TIMESTAMP,
            captured_at TIMESTAMP
        )
        """))
        self.db.commit()

    def capture_snapshot(self):
        rows = self.router.get_status_rows()

        if self.db is None:
            return rows

        self.ensure_tables()

        for row in rows:
            self.db.execute(text("""
            INSERT INTO forex_provider_telemetry(
                provider,
                health_score,
                success_count,
                failure_count,
                rate_limit_count,
                auth_error_count,
                invalid_response_count,
                avg_latency_ms,
                requests_today,
                cooldown_until,
                captured_at
            )
            VALUES(
                :provider,
                :health,
                :success,
                :failure,
                :rate_limit,
                :auth,
                :invalid,
                :latency,
                :requests,
                :cooldown,
                :captured
            )
            """),{
                "provider":row["provider"],
                "health":row["health_score"],
                "success":row["success_count"],
                "failure":row["failure_count"],
                "rate_limit":row["rate_limit_count"],
                "auth":row["auth_error_count"],
                "invalid":row["invalid_response_count"],
                "latency":row["avg_latency_ms"],
                "requests":row["requests_today"],
                "cooldown":row["cooldown_until"],
                "captured":datetime.now(timezone.utc).replace(tzinfo=None),
            })

        self.db.commit()
        return rows

    def latest(self):
        if self.db is None:
            return self.router.get_status_rows()

        self.ensure_tables()

        rows=self.db.execute(text("""
        SELECT *
        FROM forex_provider_telemetry
        ORDER BY captured_at DESC
        LIMIT 500
        """)).fetchall()

        return [dict(r._mapping) for r in rows]

    def summary(self)->dict[str,Any]:
        providers=self.router.get_status_rows()

        return{
            "captured_at":datetime.now(timezone.utc).isoformat(),
            "provider_count":len(providers),
            "providers":providers,
        }


_TELEMETRY=None

def get_forex_provider_telemetry(db=None)->ForexProviderTelemetry:
    global _TELEMETRY
    if _TELEMETRY is None or (db is not None and _TELEMETRY.db is None):
        _TELEMETRY=ForexProviderTelemetry(db)
    return _TELEMETRY
