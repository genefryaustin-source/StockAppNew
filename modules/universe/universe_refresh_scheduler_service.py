"""
modules/universe/universe_refresh_scheduler_service.py

Connects the already-built universe_refresh_scheduler.py (72-hour
per-universe due-checking, job queue, batched throttled refresh, and
analytics_snapshots update) to the running app -- confirmed nothing
called it at all before this file existed.

Why a module-level singleton, not the existing session_state-based
PortfolioScheduler pattern used elsewhere in this app: Streamlit
session_state is per-browser-session, not per-process. A scheduler
tied to it stops the moment that specific tab closes or the process
restarts (which Streamlit Community Cloud does periodically, and
after extended inactivity) -- it depends on someone remembering to
click "Start" again. A module-level singleton persists for the
lifetime of the Python process itself, independent of which user (if
any) is currently viewing the app, and this file auto-starts it
rather than requiring a manual trigger.

What this does NOT solve: if the process itself is fully asleep (no
traffic for an extended period, which free-tier Streamlit Cloud apps
can do), no in-app thread can run during that sleep -- there's no
in-app mechanism that can. The due-check logic already handles this
gracefully (next_refresh <= now just catches up whenever the app is
next visited/wakes up), which is the right behavior for a "keep
stale symbols reasonably fresh" job, not a hard real-time SLA. For a
guarantee that's fully independent of app traffic, an external
scheduled trigger (e.g. a GitHub Actions cron workflow hitting a
dedicated endpoint, or running a standalone script against the same
database) is the more robust complement to this, not a replacement
for it.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# How often the background thread wakes up to check whether any
# universe is due. This is NOT the refresh interval itself (that's
# DEFAULT_REFRESH_INTERVAL_HOURS = 72 in universe_refresh_scheduler.py)
# -- it's how frequently we check the clock. 30 minutes is frequent
# enough that a due universe won't sit un-refreshed for long, without
# constantly hitting the database to ask "is anything due yet".
DEFAULT_CHECK_INTERVAL_SECONDS = 30 * 60


class UniverseRefreshSchedulerService:
    def __init__(self, db_session_factory):
        """
        db_session_factory: a zero-argument callable returning a
        fresh DB session (e.g. modules.db.core.SessionLocal) -- not a
        single, shared session. A background thread that outlives any
        one Streamlit request needs to open and close its own
        short-lived sessions per cycle, the same pattern already
        established for this app's other module-level schedulers.
        """
        self.db_session_factory = db_session_factory
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self, *, check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS) -> None:
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(
            target=self._run_loop,
            args=(check_interval_seconds,),
            daemon=True,
        )
        self.thread.start()
        logger.info("Universe refresh scheduler started (check every %ds).", check_interval_seconds)

    def stop(self) -> None:
        self.running = False

    def _run_loop(self, check_interval_seconds: int) -> None:
        # Sleep in short ticks rather than one long time.sleep(interval)
        # so stop() takes effect promptly, matching the same rationale
        # already used for this app's other background schedulers.
        tick_seconds = 30
        elapsed_since_check = check_interval_seconds  # run an initial check immediately on start

        while self.running:
            if elapsed_since_check >= check_interval_seconds:
                self._run_due_jobs_once()
                elapsed_since_check = 0

            time.sleep(tick_seconds)
            elapsed_since_check += tick_seconds

    def _run_due_jobs_once(self) -> None:
        from modules.universe.universe_refresh_scheduler import run_due_universe_refresh_jobs

        db = self.db_session_factory()
        try:
            # max_jobs=1 per check: refreshing one universe already
            # means up to 250 symbols batched through the throttled
            # provider chain, which itself can take several minutes.
            # Checking every 30 minutes and doing at most one universe
            # per check keeps this a slow, steady background drip
            # rather than a burst that competes with real user
            # traffic for the same providers.
            result = run_due_universe_refresh_jobs(db, max_jobs=1)

            if result.get("jobs_found", 0) > 0:
                logger.info(
                    "Universe refresh cycle: %s job(s) found, %s completed, "
                    "%s symbols refreshed, %s analytics snapshots processed.",
                    result.get("jobs_found"), result.get("jobs_completed"),
                    result.get("symbols_refreshed"), result.get("analytics_processed"),
                )

        except Exception:
            logger.exception("Universe refresh cycle failed")

        finally:
            try:
                db.close()
            except Exception:
                pass


_SCHEDULER: Optional[UniverseRefreshSchedulerService] = None


def get_universe_refresh_scheduler_service(
    db_session_factory=None,
) -> Optional[UniverseRefreshSchedulerService]:
    global _SCHEDULER
    if _SCHEDULER is None and db_session_factory is not None:
        _SCHEDULER = UniverseRefreshSchedulerService(db_session_factory)
    return _SCHEDULER


def ensure_universe_refresh_scheduler_started(db_session_factory) -> None:
    """
    Idempotent auto-start entry point -- safe to call on every app
    load (e.g. from app.py's own startup path). start() itself is
    already a no-op if the scheduler is already running, so calling
    this repeatedly (once per user session that loads the app) is
    safe and does not spawn duplicate threads.
    """
    scheduler = get_universe_refresh_scheduler_service(db_session_factory)
    if scheduler is not None and not scheduler.running:
        scheduler.start()