"""
modules/market_data/provider_learning_engine.py
"""

from __future__ import annotations

from datetime import datetime, UTC
from typing import Any, Dict, List, Optional

from sqlalchemy import text


def ensure_provider_learning_tables(db):
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS provider_learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            request_type TEXT,
            symbol TEXT,
            success INTEGER DEFAULT 0,
            latency_ms REAL,
            error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_provider_learning_provider
        ON provider_learning_events(provider)
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_provider_learning_request_type
        ON provider_learning_events(request_type)
    """))

    db.commit()


class ProviderLearningEngine:
    def record_outcome(
        self,
        db,
        provider: str,
        request_type: str,
        symbol: Optional[str],
        success: bool,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> None:
        ensure_provider_learning_tables(db)

        db.execute(text("""
            INSERT INTO provider_learning_events (
                provider,
                request_type,
                symbol,
                success,
                latency_ms,
                error,
                created_at
            )
            VALUES (
                :provider,
                :request_type,
                :symbol,
                :success,
                :latency_ms,
                :error,
                :created_at
            )
        """), {
            "provider": provider.upper(),
            "request_type": request_type.upper(),
            "symbol": str(symbol or "").upper().strip() or None,
            "success": 1 if success else 0,
            "latency_ms": float(latency_ms or 0.0),
            "error": error,
            "created_at": datetime.now(UTC),
        })

    def summarize_provider_learning(
        self,
        db,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        ensure_provider_learning_tables(db)

        rows = db.execute(text("""
            SELECT
                provider,
                request_type,
                COUNT(*) AS attempts,
                SUM(success) AS successes,
                AVG(latency_ms) AS avg_latency_ms,
                MAX(created_at) AS last_seen
            FROM provider_learning_events
            GROUP BY provider, request_type
            ORDER BY provider, request_type
            LIMIT :limit
        """), {
            "limit": int(limit),
        }).fetchall()

        return [
            dict(r._mapping)
            for r in rows
        ]

    def best_provider_for_request(
        self,
        db,
        request_type: str,
    ) -> Optional[str]:
        ensure_provider_learning_tables(db)

        row = db.execute(text("""
            SELECT
                provider,
                COUNT(*) AS attempts,
                SUM(success) AS successes,
                AVG(latency_ms) AS avg_latency_ms
            FROM provider_learning_events
            WHERE request_type = :request_type
            GROUP BY provider
            HAVING COUNT(*) >= 3
            ORDER BY
                (CAST(SUM(success) AS REAL) / COUNT(*)) DESC,
                AVG(latency_ms) ASC
            LIMIT 1
        """), {
            "request_type": request_type.upper(),
        }).fetchone()

        if not row:
            return None

        return row.provider


_learning_engine = None


def get_provider_learning_engine():
    global _learning_engine

    if _learning_engine is None:
        _learning_engine = ProviderLearningEngine()

    return _learning_engine