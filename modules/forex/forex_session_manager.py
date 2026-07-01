"""
===============================================================================
Sprint 25 - Phase 2
Forex Session Manager

File:
    modules/forex/forex_session_manager.py

Purpose
-------
Centralized SQLAlchemy session lifecycle manager for the Forex platform.

Goals
-----
• Eliminate long-lived Session objects
• Automatic commit / rollback
• Automatic close
• Retry transient OperationalError failures
• Recover from PendingRollbackError
• Recover from Neon SSL disconnects
• Connection diagnostics
• Context manager support
• Thread-safe

Every Forex module should eventually use:

    with forex_session() as db:
        ...

instead of storing self.db for the lifetime of the application.

===============================================================================
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

try:
    from sqlalchemy.exc import (
        OperationalError,
        PendingRollbackError,
        DisconnectionError,
        SQLAlchemyError,
    )
    from sqlalchemy import text
except Exception:
    OperationalError = Exception
    PendingRollbackError = Exception
    DisconnectionError = Exception
    SQLAlchemyError = Exception
    text = None


# =============================================================================
# Helpers
# =============================================================================

_TRANSIENT_ERRORS = (
    "SSL connection has been closed unexpectedly",
    "server closed the connection",
    "connection already closed",
    "connection is closed",
    "terminating connection",
    "could not receive data",
    "connection reset",
)


def _utc_now():
    return datetime.now(timezone.utc)


def _is_transient(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(x.lower() in msg for x in _TRANSIENT_ERRORS)


# =============================================================================
# Session Manager
# =============================================================================


class ForexSessionManager:

    def __init__(
        self,
        session_factory=None,
        max_retries: int = 2,
    ):

        self.session_factory = session_factory
        self.max_retries = max(0, int(max_retries))

        self._lock = threading.RLock()

        self.created = _utc_now()

        self.metrics = {
            "sessions_created": 0,
            "sessions_closed": 0,
            "commits": 0,
            "rollbacks": 0,
            "retries": 0,
            "dead_sessions": 0,
            "connection_failures": 0,
            "last_error": None,
            "last_session_started": None,
        }

    # ------------------------------------------------------------------

    def create_session(self):

        if self.session_factory is None:
            raise RuntimeError(
                "ForexSessionManager requires a SQLAlchemy session factory."
            )

        session = self.session_factory()

        self.metrics["sessions_created"] += 1
        self.metrics["last_session_started"] = _utc_now()

        return session

    # ------------------------------------------------------------------

    def close_session(self, session):

        if session is None:
            return

        try:
            session.close()
        finally:
            self.metrics["sessions_closed"] += 1

    # ------------------------------------------------------------------

    def health_check(self, session):

        if session is None:
            return False

        try:

            session.rollback()

            if text is not None:
                session.execute(text("SELECT 1"))

            return True

        except Exception as exc:

            self.metrics["dead_sessions"] += 1
            self.metrics["last_error"] = str(exc)

            return False

    # ------------------------------------------------------------------

    def rollback(self, session):

        if session is None:
            return

        try:
            session.rollback()
            self.metrics["rollbacks"] += 1
        except Exception:
            pass

    # ------------------------------------------------------------------

    def commit(self, session):

        if session is None:
            return

        session.commit()

        self.metrics["commits"] += 1

    # ------------------------------------------------------------------

    @contextmanager
    def session(self):

        attempt = 0

        while True:

            db = None

            try:

                db = self.create_session()

                yield db

                self.commit(db)

                break

            except PendingRollbackError:

                self.rollback(db)

                self.metrics["retries"] += 1

                if attempt >= self.max_retries:
                    raise

            except (
                OperationalError,
                DisconnectionError,
            ) as exc:

                self.rollback(db)

                self.metrics["connection_failures"] += 1
                self.metrics["last_error"] = str(exc)

                if (
                    not _is_transient(exc)
                    or attempt >= self.max_retries
                ):
                    raise

                attempt += 1

                time.sleep(0.5)

            except SQLAlchemyError:

                self.rollback(db)
                raise

            except Exception:

                self.rollback(db)
                raise

            finally:

                self.close_session(db)

    # ------------------------------------------------------------------

    def diagnostics(self):

        age = (_utc_now() - self.created).total_seconds()

        return {
            "created": self.created.isoformat(),
            "manager_age_seconds": round(age, 1),
            **self.metrics,
        }


# =============================================================================
# Global Singleton
# =============================================================================

_MANAGER = None


def configure_forex_session_manager(session_factory):

    global _MANAGER

    _MANAGER = ForexSessionManager(
        session_factory=session_factory,
    )

    return _MANAGER


def get_forex_session_manager():

    if _MANAGER is None:

        raise RuntimeError(
            "ForexSessionManager has not been configured."
        )

    return _MANAGER


# =============================================================================
# Convenience Context Manager
# =============================================================================

@contextmanager
def forex_session():

    manager = get_forex_session_manager()

    with manager.session() as db:
        yield db


# =============================================================================
# Diagnostics
# =============================================================================

def forex_session_health():

    return get_forex_session_manager().diagnostics()