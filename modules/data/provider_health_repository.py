# modules/data/provider_health_repository.py

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any, Dict, Iterable, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


DEFAULT_PROVIDERS = [
    "POLYGON",
    "MARKETDATA",
    "FINNHUB",
    "ALPHA_VANTAGE",
    "TWELVEDATA",
    "YAHOO",
]


PROVIDER_HEALTH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS provider_health (
    provider VARCHAR(50) PRIMARY KEY,
    success_count BIGINT DEFAULT 0,
    failure_count BIGINT DEFAULT 0,
    rate_limit_count BIGINT DEFAULT 0,
    avg_latency_ms NUMERIC DEFAULT 0,
    health_score NUMERIC DEFAULT 100,
    cooldown_until TIMESTAMP,
    last_success TIMESTAMP,
    last_failure TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW()
)
"""


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        pass


def _execute(db: Session, sql: str, params: Optional[Dict[str, Any]] = None):
    return db.execute(text(sql), params or {})


def ensure_provider_health_table(db: Session) -> None:
    _execute(db, PROVIDER_HEALTH_TABLE_SQL)
    _execute(db, "CREATE INDEX IF NOT EXISTS idx_provider_health_score ON provider_health(health_score)")
    db.commit()


def upsert_provider_baseline(db: Session, provider: str, health_score: float = 100.0) -> None:
    provider_name = str(provider or "").upper().strip()
    if not provider_name:
        return
    _execute(
        db,
        """
        INSERT INTO provider_health (
            provider, health_score, success_count, failure_count,
            rate_limit_count, avg_latency_ms, updated_at
        )
        VALUES (:provider, :health_score, 0, 0, 0, 0, NOW())
        ON CONFLICT (provider) DO NOTHING
        """,
        {"provider": provider_name, "health_score": float(health_score)},
    )


def seed_provider_health(db: Session, providers: Optional[Iterable[str]] = None) -> None:
    ensure_provider_health_table(db)
    for provider in providers or DEFAULT_PROVIDERS:
        upsert_provider_baseline(db, provider)
    db.commit()


def record_provider_success(db: Session, provider: str, latency_ms: Optional[float] = None) -> None:
    ensure_provider_health_table(db)
    provider_name = str(provider or "").upper().strip()
    if not provider_name:
        return
    upsert_provider_baseline(db, provider_name)
    latency = float(latency_ms or 0)
    _execute(
        db,
        """
        UPDATE provider_health
        SET success_count = COALESCE(success_count, 0) + 1,
            avg_latency_ms = CASE
                WHEN :latency_ms <= 0 THEN COALESCE(avg_latency_ms, 0)
                WHEN COALESCE(avg_latency_ms, 0) <= 0 THEN :latency_ms
                ELSE ROUND(((COALESCE(avg_latency_ms, 0) * 0.85) + (:latency_ms * 0.15))::numeric, 2)
            END,
            health_score = LEAST(100, COALESCE(health_score, 100) + 1),
            cooldown_until = NULL,
            last_success = NOW(),
            updated_at = NOW()
        WHERE provider = :provider
        """,
        {"provider": provider_name, "latency_ms": latency},
    )
    db.commit()


def record_provider_failure(db: Session, provider: str, penalty: float = 5.0) -> None:
    ensure_provider_health_table(db)
    provider_name = str(provider or "").upper().strip()
    if not provider_name:
        return
    upsert_provider_baseline(db, provider_name)
    _execute(
        db,
        """
        UPDATE provider_health
        SET failure_count = COALESCE(failure_count, 0) + 1,
            health_score = GREATEST(0, COALESCE(health_score, 100) - :penalty),
            last_failure = NOW(),
            updated_at = NOW()
        WHERE provider = :provider
        """,
        {"provider": provider_name, "penalty": float(penalty)},
    )
    db.commit()


def record_provider_rate_limit(
    db: Session,
    provider: str,
    cooldown_minutes: int = 15,
    penalty: float = 10.0,
) -> None:
    ensure_provider_health_table(db)
    provider_name = str(provider or "").upper().strip()
    if not provider_name:
        return
    upsert_provider_baseline(db, provider_name)
    cooldown_until = _now() + timedelta(minutes=int(cooldown_minutes or 15))
    _execute(
        db,
        """
        UPDATE provider_health
        SET rate_limit_count = COALESCE(rate_limit_count, 0) + 1,
            failure_count = COALESCE(failure_count, 0) + 1,
            health_score = GREATEST(0, COALESCE(health_score, 100) - :penalty),
            cooldown_until = :cooldown_until,
            last_failure = NOW(),
            updated_at = NOW()
        WHERE provider = :provider
        """,
        {"provider": provider_name, "penalty": float(penalty), "cooldown_until": cooldown_until},
    )
    db.commit()


def get_provider_health_rows(db: Session) -> list[dict[str, Any]]:
    ensure_provider_health_table(db)
    try:
        rows = _execute(
            db,
            """
            SELECT provider,
                   COALESCE(health_score, 0) AS health_score,
                   COALESCE(success_count, 0) AS success_count,
                   COALESCE(failure_count, 0) AS failure_count,
                   COALESCE(rate_limit_count, 0) AS rate_limit_count,
                   COALESCE(avg_latency_ms, 0) AS avg_latency_ms,
                   cooldown_until,
                   last_success,
                   last_failure,
                   updated_at
            FROM provider_health
            ORDER BY provider
            """,
        ).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        _safe_rollback(db)
        return []


def get_provider_health_summary(db: Session) -> dict[str, Any]:
    ensure_provider_health_table(db)
    row = _execute(
        db,
        """
        SELECT COALESCE(SUM(success_count), 0) AS successes,
               COALESCE(SUM(failure_count), 0) AS failures,
               COALESCE(SUM(rate_limit_count), 0) AS rate_limits,
               COALESCE(AVG(avg_latency_ms), 0) AS avg_latency_ms,
               COALESCE(AVG(health_score), 0) AS avg_health_score,
               COUNT(*) AS providers,
               COUNT(*) FILTER (WHERE cooldown_until IS NULL OR cooldown_until <= NOW()) AS available_providers
        FROM provider_health
        """,
    ).mappings().first()
    if not row:
        return {"successes": 0, "failures": 0, "rate_limits": 0, "success_rate": 0.0, "avg_latency_ms": 0.0, "avg_health_score": 0.0, "providers": 0, "available_providers": 0}
    data = dict(row)
    successes = float(data.get("successes") or 0)
    failures = float(data.get("failures") or 0)
    total = successes + failures
    data["success_rate"] = round((successes / total) * 100, 2) if total else 0.0
    data["avg_latency_ms"] = round(float(data.get("avg_latency_ms") or 0), 2)
    data["avg_health_score"] = round(float(data.get("avg_health_score") or 0), 2)
    return data
