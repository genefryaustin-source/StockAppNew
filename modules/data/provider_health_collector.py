# modules/data/provider_health_collector.py

from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy.orm import Session

from modules.data.provider_health_service import (
    initialize_provider_health,
    mark_provider_failure,
    mark_provider_rate_limited,
    mark_provider_success,
)

from modules.db.core import new_db_session

def bootstrap_provider_health(db: Session, providers: Optional[Iterable[str]] = None) -> None:
    initialize_provider_health(db, providers=providers)


def provider_success(db: Session, provider: str, latency_ms: Optional[float] = None) -> None:
    mark_provider_success(db, provider, latency_ms=latency_ms)


def provider_failure(db: Session, provider: str, penalty: float = 5.0) -> None:
    mark_provider_failure(db, provider, penalty=penalty)


def provider_rate_limited(
    db: Session,
    provider: str,
    cooldown_minutes: int = 15,
    penalty: float = 10.0,
) -> None:
    mark_provider_rate_limited(
        db,
        provider,
        cooldown_minutes=cooldown_minutes,
        penalty=penalty,
    )


def attach_provider_health_to_router(router: Any, db: Session) -> Any:
    if router is None:
        return router
    if hasattr(router, "mark_success"):
        original_success = router.mark_success


        def wrapped_success(provider: str, *args, **kwargs):
            try:
                local_db = new_db_session()

                try:
                    provider_success(
                        local_db,
                        provider,
                        latency_ms=kwargs.get("latency_ms")
                    )
                finally:
                    local_db.close()

            except Exception as exc:
                print(
                    "Provider health success write failed:",
                    exc,
                )

            return original_success(
                provider,
                *args,
                **kwargs,
            )
    if hasattr(router, "mark_failure"):
        original_failure = router.mark_failure
        def wrapped_failure(provider: str, *args, **kwargs):
            try:
                provider_failure(db, provider)
            except Exception as exc:
                print("Provider health failure write failed:", exc)
            return original_failure(provider, *args, **kwargs)
        router.mark_failure = wrapped_failure
    if hasattr(router, "mark_rate_limited"):
        original_rate_limited = router.mark_rate_limited
        def wrapped_rate_limited(provider: str, *args, **kwargs):
            try:
                provider_rate_limited(db, provider, cooldown_minutes=kwargs.get("cooldown_minutes", 15))
            except Exception as exc:
                print("Provider health rate-limit write failed:", exc)
            return original_rate_limited(provider, *args, **kwargs)
        router.mark_rate_limited = wrapped_rate_limited
    return router
