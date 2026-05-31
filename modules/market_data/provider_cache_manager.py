"""
modules/market_data/provider_cache_manager.py
"""

from __future__ import annotations

from datetime import datetime, UTC, timedelta
from typing import Any, Optional

from sqlalchemy import text


DEFAULT_PROFILE_TTL_HOURS = 24
DEFAULT_FUNDAMENTAL_TTL_HOURS = 24
DEFAULT_NEWS_TTL_HOURS = 6


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_provider_cache_tables(db) -> None:
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS provider_cache (
            cache_key TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            symbol TEXT,
            data_type TEXT NOT NULL,
            payload TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            expires_at DATETIME
        )
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_provider_cache_symbol_type
        ON provider_cache(symbol, data_type)
    """))

    db.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_provider_cache_expires
        ON provider_cache(expires_at)
    """))

    db.commit()


def build_cache_key(
    provider: str,
    data_type: str,
    symbol: Optional[str] = None,
) -> str:
    sym = str(symbol or "").upper().strip()
    return f"{provider.upper()}:{data_type.upper()}:{sym}"


def get_cached_payload(
    db,
    provider: str,
    data_type: str,
    symbol: Optional[str] = None,
) -> Optional[str]:
    ensure_provider_cache_tables(db)

    key = build_cache_key(
        provider=provider,
        data_type=data_type,
        symbol=symbol,
    )

    row = db.execute(text("""
        SELECT payload, expires_at
        FROM provider_cache
        WHERE cache_key = :cache_key
        LIMIT 1
    """), {
        "cache_key": key,
    }).fetchone()

    if not row:
        return None

    expires_at = row.expires_at

    if expires_at and expires_at <= utc_now():
        return None

    return row.payload


def set_cached_payload(
    db,
    provider: str,
    data_type: str,
    payload: str,
    symbol: Optional[str] = None,
    ttl_hours: int = DEFAULT_FUNDAMENTAL_TTL_HOURS,
) -> None:
    ensure_provider_cache_tables(db)

    now = utc_now()
    expires_at = now + timedelta(hours=int(ttl_hours))
    key = build_cache_key(
        provider=provider,
        data_type=data_type,
        symbol=symbol,
    )

    db.execute(text("""
        INSERT INTO provider_cache (
            cache_key,
            provider,
            symbol,
            data_type,
            payload,
            created_at,
            updated_at,
            expires_at
        )
        VALUES (
            :cache_key,
            :provider,
            :symbol,
            :data_type,
            :payload,
            :created_at,
            :updated_at,
            :expires_at
        )
        ON CONFLICT(cache_key) DO UPDATE SET
            payload = excluded.payload,
            updated_at = excluded.updated_at,
            expires_at = excluded.expires_at
    """), {
        "cache_key": key,
        "provider": provider.upper(),
        "symbol": str(symbol or "").upper().strip() or None,
        "data_type": data_type.upper(),
        "payload": payload,
        "created_at": now,
        "updated_at": now,
        "expires_at": expires_at,
    })


def clear_expired_provider_cache(db) -> int:
    ensure_provider_cache_tables(db)

    result = db.execute(text("""
        DELETE FROM provider_cache
        WHERE expires_at IS NOT NULL
        AND expires_at <= :now
    """), {
        "now": utc_now(),
    })

    db.commit()

    return int(result.rowcount or 0)


def get_provider_cache_status(db):
    ensure_provider_cache_tables(db)

    rows = db.execute(text("""
        SELECT
            provider,
            data_type,
            COUNT(*) AS records,
            MIN(expires_at) AS oldest_expiry,
            MAX(updated_at) AS latest_update
        FROM provider_cache
        GROUP BY provider, data_type
        ORDER BY provider, data_type
    """)).fetchall()

    return [
        dict(r._mapping)
        for r in rows
    ]