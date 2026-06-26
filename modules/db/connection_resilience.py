"""
modules/db/connection_resilience.py

Shared helper for recovering from a dropped Postgres connection mid-job --
the classic Neon-serverless symptom (SSL connection has been closed
unexpectedly / server closed the connection unexpectedly / connection
reset by peer). pool_pre_ping and pool_recycle only protect a connection
sitting idle *in the pool* between checkouts; they don't help a
connection that's been checked out for a long-running job (many minutes,
many external API calls) and dies server-side mid-use.

This exact pattern has been applied individually in:
    modules/analytics/runner.py        (run_vectorized_price_analytics, run_analytics)
    modules/agent/agent_engine.py      (_get_live_prices)
    modules/digest/holdings_explainer.py (_load_price_changes)
    modules/alerts/scanner_engine.py   (run_scanner_rule)
    modules/analytics/strategy_lab_ui.py (_compute_factor_scores_from_price)

New code should import from here instead of redefining its own copy.
The five files above are already deployed and tested with their own
local copies -- left as-is rather than retrofitted, to avoid touching
working code without need. Consider migrating them here later if it's
ever convenient to do as a batch.
"""

from __future__ import annotations

from typing import Optional


def is_dead_connection_error(e: Exception) -> bool:
    """True if `e` looks like a dropped/expired database connection
    rather than a genuine data/query error that a retry wouldn't fix."""
    msg = str(e).lower()
    return any(s in msg for s in (
        "ssl connection has been closed",
        "server closed the connection unexpectedly",
        "connection already closed",
        "could not connect to server",
        "connection reset by peer",
        "terminating connection",
    ))


def get_fresh_session():
    from modules.db.core import SessionLocal
    return SessionLocal()


def with_connection_recovery(db, fn, *args, on_reconnect=None, **kwargs):
    """Call fn(db, *args, **kwargs). If it fails with a dead-connection
    error, roll back and close the old session, get a fresh one, call
    on_reconnect(new_db) if given (e.g. to re-fetch an ORM row bound to
    the old session), and retry exactly once with the fresh session.

    Returns (result, db) -- always use the returned `db` afterward, since
    it may be a different session than the one you passed in.
    """
    try:
        result = fn(db, *args, **kwargs)
        return result, db
    except Exception as e:
        if not is_dead_connection_error(e):
            raise

        try:
            db.rollback()
        except Exception:
            pass
        try:
            db.close()
        except Exception:
            pass

        new_db = get_fresh_session()

        if on_reconnect:
            on_reconnect(new_db)

        result = fn(new_db, *args, **kwargs)
        return result, new_db