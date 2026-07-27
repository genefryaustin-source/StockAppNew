# modules/data/provider_health_service.py

from __future__ import annotations

from typing import Any, Iterable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from modules.data.provider_health_repository import (
    DEFAULT_PROVIDERS,
    ensure_provider_health_table,
    get_provider_health_rows,
    get_provider_health_summary,
    record_provider_failure,
    record_provider_rate_limit,
    record_provider_success,
    seed_provider_health,
)


def initialize_provider_health(db: Session, providers: Optional[Iterable[str]] = None) -> None:
    seed_provider_health(db, providers or DEFAULT_PROVIDERS)


def mark_provider_success(db: Session, provider: str, latency_ms: Optional[float] = None) -> None:
    record_provider_success(db, provider, latency_ms=latency_ms)


def mark_provider_failure(db: Session, provider: str, penalty: float = 5.0) -> None:
    record_provider_failure(db, provider, penalty=penalty)


def mark_provider_rate_limited(
    db: Session,
    provider: str,
    cooldown_minutes: int = 15,
    penalty: float = 10.0,
) -> None:
    record_provider_rate_limit(
        db,
        provider,
        cooldown_minutes=cooldown_minutes,
        penalty=penalty,
    )


def provider_health_dataframe(db: Session) -> pd.DataFrame:
    rows = get_provider_health_rows(db)
    df = pd.DataFrame(rows)
    columns = [
        "Provider",
        "Health",
        "Successes",
        "Failures",
        "Rate Limits",
        "Avg Latency",
        "Cooldown Until",
        "Last Success",
        "Last Failure",
        "Updated",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)
    df = df.rename(
        columns={
            "provider": "Provider",
            "health_score": "Health",
            "success_count": "Successes",
            "failure_count": "Failures",
            "rate_limit_count": "Rate Limits",
            "avg_latency_ms": "Avg Latency",
            "cooldown_until": "Cooldown Until",
            "last_success": "Last Success",
            "last_failure": "Last Failure",
            "updated_at": "Updated",
        }
    )
    for col in ["Health", "Avg Latency"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round(2)
    for col in ["Successes", "Failures", "Rate Limits"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in columns:
        if col not in df.columns:
            df[col] = None
    return df[columns]


def provider_health_metrics(db: Session) -> dict[str, Any]:
    ensure_provider_health_table(db)
    return get_provider_health_summary(db)


def record_provider_event(
    db: Session,
    provider: str,
    event_type: str,
    latency_ms: Optional[float] = None,
    cooldown_minutes: int = 15,
) -> None:
    event = str(event_type or "").lower().strip()
    if event in {"success", "ok", "pass"}:
        mark_provider_success(db, provider, latency_ms=latency_ms)
        return
    if event in {"rate_limit", "ratelimit", "limited", "429"}:
        mark_provider_rate_limited(db, provider, cooldown_minutes=cooldown_minutes)
        return
    mark_provider_failure(db, provider)
