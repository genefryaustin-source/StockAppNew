"""
modules/forex/forex_database_session_manager.py

Sprint 26 - Phase 1
Forex Database Session Manager

Purpose
-------
Centralized database session reliability layer for the Forex subsystem.

This module is designed to solve the Neon/Postgres stale-session failure pattern
seen during long Streamlit dashboard renders:

    SSL connection has been closed unexpectedly
    PendingRollbackError
    Can't reconnect until invalid transaction is rolled back

Core features
-------------
- Lightweight session health checks using SELECT 1
- Safe rollback that does not crash when the connection is already dead
- Dead-session detection
- Optional short-lived session factory support
- Retry wrapper for transient OperationalError / disconnect failures
- Query timing / diagnostics counters
- Context-manager helpers for read/write operations
- Backward-compatible helpers for modules that still receive a long-lived db

Recommended usage
-----------------
Configure once during app/bootstrap if you have a session factory:

    from modules.forex.forex_database_session_manager import (
        configure_forex_database_session_manager,
    )

    configure_forex_database_session_manager(SessionLocal)

Then use:

    from modules.forex.forex_database_session_manager import forex_db_session

    with forex_db_session() as db:
        rows = db.execute(text("SELECT 1")).fetchall()

For modules that still receive a db object:

    from modules.forex.forex_database_session_manager import (
        get_forex_database_session_manager,
    )

    manager = get_forex_database_session_manager()
    if not manager.is_session_usable(self.db):
        ...

Notes
-----
This manager cannot magically recreate a caller-owned SQLAlchemy Session object
that was created elsewhere and is already dead. It can detect it, safely attempt
rollback, and report it. To fully eliminate stale sessions, managers should
eventually use this module's short-lived `session()` context manager.

"""

from __future__ import annotations

import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, Optional, Tuple


try:
    from sqlalchemy import text
    from sqlalchemy.exc import (
        DBAPIError,
        DisconnectionError,
        InterfaceError,
        InvalidRequestError,
        OperationalError,
        PendingRollbackError,
        SQLAlchemyError,
    )
except Exception:  # pragma: no cover - lets module import without SQLAlchemy
    text = None
    DBAPIError = Exception
    DisconnectionError = Exception
    InterfaceError = Exception
    InvalidRequestError = Exception
    OperationalError = Exception
    PendingRollbackError = Exception
    SQLAlchemyError = Exception


# =============================================================================
# Constants / helpers
# =============================================================================

TRANSIENT_ERROR_PATTERNS = (
    "ssl connection has been closed unexpectedly",
    "server closed the connection",
    "connection already closed",
    "connection is closed",
    "terminating connection",
    "could not receive data",
    "connection reset",
    "connection refused",
    "connection not open",
    "connection was closed",
    "closed the connection unexpectedly",
    "lost synchronization",
    "unexpected eof",
    "pendingrollbackerror",
    "can't reconnect until invalid transaction is rolled back",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


def safe_error(exc: BaseException) -> str:
    try:
        return str(exc)
    except Exception:
        return repr(exc)


def is_transient_database_error(exc: BaseException) -> bool:
    msg = safe_error(exc).lower()
    return any(pattern in msg for pattern in TRANSIENT_ERROR_PATTERNS)


def is_disconnect_error(exc: BaseException) -> bool:
    if isinstance(exc, (OperationalError, DisconnectionError, InterfaceError)):
        return True
    if isinstance(exc, DBAPIError):
        return bool(getattr(exc, "connection_invalidated", False))
    return is_transient_database_error(exc)


def _session_identity(session: Any) -> str:
    if session is None:
        return "none"
    return f"{type(session).__name__}:{id(session)}"


# =============================================================================
# Diagnostics models
# =============================================================================

@dataclass
class ForexDatabaseSessionMetrics:
    manager_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_iso)

    sessions_created: int = 0
    sessions_closed: int = 0

    health_checks: int = 0
    health_check_failures: int = 0

    commits: int = 0
    commit_failures: int = 0

    rollbacks: int = 0
    rollback_failures: int = 0

    retries: int = 0
    operations: int = 0
    operation_failures: int = 0
    transient_failures: int = 0
    dead_sessions: int = 0

    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    last_success_at: Optional[str] = None

    total_query_ms: float = 0.0
    max_query_ms: float = 0.0
    last_query_ms: float = 0.0

    def record_error(self, exc: BaseException) -> None:
        self.last_error = safe_error(exc)
        self.last_error_at = utc_iso()

    def record_query_time(self, elapsed_ms: float) -> None:
        value = float(elapsed_ms)
        self.last_query_ms = round(value, 3)
        self.total_query_ms = round(self.total_query_ms + value, 3)
        self.max_query_ms = round(max(self.max_query_ms, value), 3)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "manager_id": self.manager_id,
            "created_at": self.created_at,
            "sessions_created": self.sessions_created,
            "sessions_closed": self.sessions_closed,
            "health_checks": self.health_checks,
            "health_check_failures": self.health_check_failures,
            "commits": self.commits,
            "commit_failures": self.commit_failures,
            "rollbacks": self.rollbacks,
            "rollback_failures": self.rollback_failures,
            "retries": self.retries,
            "operations": self.operations,
            "operation_failures": self.operation_failures,
            "transient_failures": self.transient_failures,
            "dead_sessions": self.dead_sessions,
            "last_error": self.last_error,
            "last_error_at": self.last_error_at,
            "last_success_at": self.last_success_at,
            "total_query_ms": self.total_query_ms,
            "max_query_ms": self.max_query_ms,
            "last_query_ms": self.last_query_ms,
        }


@dataclass
class SessionHealthReport:
    usable: bool
    session_id: str
    checked_at: str
    error: Optional[str] = None
    rollback_ok: Optional[bool] = None
    select_ok: Optional[bool] = None
    elapsed_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "usable": self.usable,
            "session_id": self.session_id,
            "checked_at": self.checked_at,
            "error": self.error,
            "rollback_ok": self.rollback_ok,
            "select_ok": self.select_ok,
            "elapsed_ms": self.elapsed_ms,
        }


# =============================================================================
# Manager
# =============================================================================

class ForexDatabaseSessionManager:
    """
    Centralized SQLAlchemy session reliability manager.

    The manager supports both:
      1. Factory-owned short-lived sessions through `session()`
      2. Caller-owned legacy sessions through health helpers
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
        *,
        max_retries: int = 1,
        retry_sleep_seconds: float = 0.35,
        validate_on_checkout: bool = True,
        echo: bool = False,
    ) -> None:
        self.session_factory = session_factory
        self.max_retries = max(0, int(max_retries))
        self.retry_sleep_seconds = max(0.0, float(retry_sleep_seconds))
        self.validate_on_checkout = bool(validate_on_checkout)
        self.echo = bool(echo)

        self._lock = threading.RLock()
        self.metrics = ForexDatabaseSessionMetrics()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        if self.echo:
            print(f"[FOREX DB SESSION] {message}")

    # ------------------------------------------------------------------
    # Session creation / close
    # ------------------------------------------------------------------

    def configure(self, session_factory: Callable[[], Any]) -> None:
        with self._lock:
            self.session_factory = session_factory

    def create_session(self) -> Any:
        if self.session_factory is None:
            raise RuntimeError(
                "ForexDatabaseSessionManager is not configured with a session_factory."
            )

        db = self.session_factory()

        with self._lock:
            self.metrics.sessions_created += 1

        self._log(f"created session {_session_identity(db)}")

        if self.validate_on_checkout:
            report = self.health_check(db)
            if not report.usable:
                self.safe_close(db)
                raise RuntimeError(
                    f"Created database session failed health check: {report.error}"
                )

        return db

    def safe_close(self, session: Any) -> None:
        if session is None:
            return

        try:
            session.close()
        except Exception as exc:
            self._record_error(exc)
        finally:
            with self._lock:
                self.metrics.sessions_closed += 1

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def safe_rollback(self, session: Any) -> bool:
        if session is None:
            return False

        try:
            session.rollback()
            with self._lock:
                self.metrics.rollbacks += 1
            return True
        except Exception as exc:
            with self._lock:
                self.metrics.rollback_failures += 1
                self.metrics.dead_sessions += 1
                self.metrics.record_error(exc)
            self._log(f"rollback failed on {_session_identity(session)}: {exc}")
            return False

    def safe_commit(self, session: Any) -> bool:
        if session is None:
            return False

        try:
            session.commit()
            with self._lock:
                self.metrics.commits += 1
                self.metrics.last_success_at = utc_iso()
            return True
        except Exception as exc:
            with self._lock:
                self.metrics.commit_failures += 1
                self.metrics.record_error(exc)
            self.safe_rollback(session)
            return False

    def health_check(self, session: Any) -> SessionHealthReport:
        started = time.perf_counter()
        sid = _session_identity(session)

        with self._lock:
            self.metrics.health_checks += 1

        if session is None:
            with self._lock:
                self.metrics.health_check_failures += 1
                self.metrics.dead_sessions += 1

            return SessionHealthReport(
                usable=False,
                session_id=sid,
                checked_at=utc_iso(),
                error="Session is None.",
                rollback_ok=False,
                select_ok=False,
                elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            )

        rollback_ok = self.safe_rollback(session)

        if not rollback_ok:
            with self._lock:
                self.metrics.health_check_failures += 1

            return SessionHealthReport(
                usable=False,
                session_id=sid,
                checked_at=utc_iso(),
                error="Rollback failed; session is likely dead.",
                rollback_ok=False,
                select_ok=False,
                elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            )

        if text is None:
            return SessionHealthReport(
                usable=True,
                session_id=sid,
                checked_at=utc_iso(),
                rollback_ok=True,
                select_ok=None,
                elapsed_ms=round((time.perf_counter() - started) * 1000.0, 3),
            )

        try:
            session.execute(text("SELECT 1"))
            elapsed = (time.perf_counter() - started) * 1000.0
            with self._lock:
                self.metrics.last_success_at = utc_iso()
                self.metrics.record_query_time(elapsed)

            return SessionHealthReport(
                usable=True,
                session_id=sid,
                checked_at=utc_iso(),
                rollback_ok=True,
                select_ok=True,
                elapsed_ms=round(elapsed, 3),
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - started) * 1000.0
            with self._lock:
                self.metrics.health_check_failures += 1
                self.metrics.dead_sessions += 1
                self.metrics.record_error(exc)
                self.metrics.record_query_time(elapsed)

            return SessionHealthReport(
                usable=False,
                session_id=sid,
                checked_at=utc_iso(),
                error=safe_error(exc),
                rollback_ok=True,
                select_ok=False,
                elapsed_ms=round(elapsed, 3),
            )

    def is_session_usable(self, session: Any) -> bool:
        return self.health_check(session).usable

    # ------------------------------------------------------------------
    # Context managers
    # ------------------------------------------------------------------

    @contextmanager
    def session(
        self,
        *,
        commit: bool = False,
        close: bool = True,
        validate: Optional[bool] = None,
    ) -> Iterator[Any]:
        """
        Short-lived session context.

        commit=False is ideal for read-only dashboard operations.
        commit=True commits at the end and rolls back on error.
        """

        db = None
        try:
            db = self.create_session()

            should_validate = self.validate_on_checkout if validate is None else bool(validate)
            if should_validate:
                report = self.health_check(db)
                if not report.usable:
                    raise RuntimeError(f"Database session failed health check: {report.error}")

            yield db

            if commit:
                if not self.safe_commit(db):
                    raise RuntimeError("Database commit failed.")

        except Exception:
            if db is not None:
                self.safe_rollback(db)
            raise

        finally:
            if close:
                self.safe_close(db)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self.session(commit=True, close=True) as db:
            yield db

    @contextmanager
    def readonly(self) -> Iterator[Any]:
        with self.session(commit=False, close=True) as db:
            yield db

    # ------------------------------------------------------------------
    # Retry execution helpers
    # ------------------------------------------------------------------

    def execute_with_retry(
        self,
        operation: Callable[[Any], Any],
        *,
        session: Any = None,
        commit: bool = False,
        close_external_session: bool = False,
        operation_name: str = "database_operation",
    ) -> Any:
        """
        Execute operation(db) with retry on transient disconnects.

        If `session` is provided, it is considered caller-owned. If that session
        is dead, retry requires a configured session_factory so the manager can
        create a replacement session.
        """

        last_error: Optional[BaseException] = None

        for attempt in range(self.max_retries + 1):
            db = session
            created_here = False
            started = time.perf_counter()

            try:
                if db is None or attempt > 0:
                    db = self.create_session()
                    created_here = True
                else:
                    report = self.health_check(db)
                    if not report.usable:
                        if self.session_factory is None:
                            raise RuntimeError(
                                f"Caller-owned session is not usable: {report.error}"
                            )
                        db = self.create_session()
                        created_here = True

                result = operation(db)

                if commit:
                    if not self.safe_commit(db):
                        raise RuntimeError(f"{operation_name}: commit failed.")

                elapsed = (time.perf_counter() - started) * 1000.0
                with self._lock:
                    self.metrics.operations += 1
                    self.metrics.last_success_at = utc_iso()
                    self.metrics.record_query_time(elapsed)

                return result

            except Exception as exc:
                last_error = exc
                transient = is_disconnect_error(exc) or is_transient_database_error(exc)

                with self._lock:
                    self.metrics.operation_failures += 1
                    self.metrics.record_error(exc)
                    if transient:
                        self.metrics.transient_failures += 1

                self.safe_rollback(db)

                if not transient or attempt >= self.max_retries:
                    raise

                with self._lock:
                    self.metrics.retries += 1

                self._log(
                    f"{operation_name} transient failure attempt={attempt + 1}: {exc}"
                )

                time.sleep(self.retry_sleep_seconds * (attempt + 1))

            finally:
                if created_here:
                    self.safe_close(db)
                elif close_external_session:
                    self.safe_close(db)

        if last_error is not None:
            raise last_error

        raise RuntimeError(f"{operation_name} failed for unknown reason.")

    def execute_sql(
        self,
        sql: Any,
        params: Optional[Dict[str, Any]] = None,
        *,
        session: Any = None,
        fetch: Optional[str] = None,
        commit: bool = False,
        operation_name: str = "execute_sql",
    ) -> Any:
        """
        Execute SQL safely.

        fetch:
          - None: return SQLAlchemy result object
          - "all": return list of rows
          - "one": return one row or None
          - "scalar": return scalar value
        """

        def op(db):
            statement = text(sql) if isinstance(sql, str) and text is not None else sql
            result = db.execute(statement, params or {})
            if fetch == "all":
                return result.fetchall()
            if fetch == "one":
                return result.fetchone()
            if fetch == "scalar":
                return result.scalar()
            return result

        return self.execute_with_retry(
            op,
            session=session,
            commit=commit,
            operation_name=operation_name,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def diagnostics(self) -> Dict[str, Any]:
        with self._lock:
            return self.metrics.to_dict()

    def reset_metrics(self) -> Dict[str, Any]:
        with self._lock:
            self.metrics = ForexDatabaseSessionMetrics()
            return self.metrics.to_dict()

    def _record_error(self, exc: BaseException) -> None:
        with self._lock:
            self.metrics.record_error(exc)


# =============================================================================
# Singleton helpers
# =============================================================================

_MANAGER: Optional[ForexDatabaseSessionManager] = None
_MANAGER_LOCK = threading.RLock()


def configure_forex_database_session_manager(
    session_factory: Callable[[], Any],
    *,
    max_retries: int = 1,
    retry_sleep_seconds: float = 0.35,
    validate_on_checkout: bool = True,
    echo: bool = False,
) -> ForexDatabaseSessionManager:
    global _MANAGER

    with _MANAGER_LOCK:
        _MANAGER = ForexDatabaseSessionManager(
            session_factory=session_factory,
            max_retries=max_retries,
            retry_sleep_seconds=retry_sleep_seconds,
            validate_on_checkout=validate_on_checkout,
            echo=echo,
        )
        return _MANAGER


def get_forex_database_session_manager(
    session_factory: Optional[Callable[[], Any]] = None,
) -> ForexDatabaseSessionManager:
    global _MANAGER

    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = ForexDatabaseSessionManager(
                session_factory=session_factory,
            )
        elif session_factory is not None and _MANAGER.session_factory is None:
            _MANAGER.configure(session_factory)

        return _MANAGER


@contextmanager
def forex_db_session(
    *,
    commit: bool = False,
    close: bool = True,
    validate: Optional[bool] = None,
) -> Iterator[Any]:
    manager = get_forex_database_session_manager()
    with manager.session(commit=commit, close=close, validate=validate) as db:
        yield db


@contextmanager
def forex_db_transaction() -> Iterator[Any]:
    manager = get_forex_database_session_manager()
    with manager.transaction() as db:
        yield db


@contextmanager
def forex_db_readonly() -> Iterator[Any]:
    manager = get_forex_database_session_manager()
    with manager.readonly() as db:
        yield db


def forex_database_session_diagnostics() -> Dict[str, Any]:
    return get_forex_database_session_manager().diagnostics()


def is_forex_session_usable(session: Any) -> bool:
    return get_forex_database_session_manager().is_session_usable(session)


def forex_safe_rollback(session: Any) -> bool:
    return get_forex_database_session_manager().safe_rollback(session)


def forex_safe_close(session: Any) -> None:
    return get_forex_database_session_manager().safe_close(session)


__all__ = [
    "ForexDatabaseSessionManager",
    "ForexDatabaseSessionMetrics",
    "SessionHealthReport",
    "configure_forex_database_session_manager",
    "get_forex_database_session_manager",
    "forex_db_session",
    "forex_db_transaction",
    "forex_db_readonly",
    "forex_database_session_diagnostics",
    "is_forex_session_usable",
    "forex_safe_rollback",
    "forex_safe_close",
    "is_transient_database_error",
    "is_disconnect_error",
]
