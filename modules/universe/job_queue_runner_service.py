"""
modules/universe/job_queue_runner_service.py

Connects the "jobs" queue (modules/jobs/models.py, driven by
job_runner.py -- the manual "Universe Refresh Engine" UI) to a
background thread that automatically picks up and runs any queued
job, so a large universe's stale backlog keeps getting processed in
successive batches without anyone needing to click "Run Next Job"
again after each one finishes.

This is a genuinely different system from
universe_refresh_scheduler_service.py (which drives the separate
universe_refresh_jobs table and its 72-hour due-checking cadence).
This one exists specifically to make the manual job queue
self-driving once a job is sitting there with status="queued" --
job_runner.py's own auto-requeue logic (added alongside this file)
is what actually creates that follow-up "queued" row when a batch
finishes with real progress made but backlog still remaining; this
service is what notices it and runs it, without a browser tab open
or a button clicked.

Why a short (30s) check interval, unlike the other scheduler's 30
minutes: this queue is meant to be drained promptly and continuously
while there's real work queued, not checked for "is it due yet"
against a multi-day cadence.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CHECK_INTERVAL_SECONDS = 30


class JobQueueRunnerService:
    def __init__(self, db_session_factory):
        """
        db_session_factory: a zero-argument callable returning a
        fresh DB session, matching the pattern already established
        for this app's other module-level background services -- a
        background thread that outlives any one Streamlit request
        needs to open and close its own short-lived sessions per
        cycle, not share one long-lived session across the whole
        process lifetime.
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
        logger.info("Job queue runner started (check every %ds).", check_interval_seconds)

    def stop(self) -> None:
        self.running = False

    def _run_loop(self, check_interval_seconds: int) -> None:
        # Sleep in short ticks so stop() takes effect promptly,
        # matching the same rationale used elsewhere in this app.
        tick_seconds = 5
        elapsed_since_check = check_interval_seconds

        while self.running:
            if elapsed_since_check >= check_interval_seconds:
                self._run_one_queued_job_if_any()
                elapsed_since_check = 0

            time.sleep(tick_seconds)
            elapsed_since_check += tick_seconds

    def _run_one_queued_job_if_any(self) -> None:
        from modules.jobs.models import Job
        from modules.universe.job_runner import run_one_queued_job

        db = self.db_session_factory()
        tenant_id = None
        universe_id = None
        found_job = False

        try:
            # Find the oldest queued universe_refresh job across any
            # tenant/universe -- run_one_queued_job() itself already
            # scopes correctly by tenant_id once given one, so this
            # just needs to find *a* queued job to hand off to it.
            job = (
                db.query(Job)
                .filter(Job.status == "queued", Job.job_type == "universe_refresh")
                .order_by(Job.created_at.asc())
                .first()
            )

            if job is not None:
                found_job = True
                tenant_id = job.tenant_id
                universe_id = job.universe_id

        except Exception:
            logger.exception("Job queue runner: failed to look up a queued job")
        finally:
            # This must run on every path -- found a job, found
            # nothing (the common case when idle), or hit an
            # exception -- otherwise this session is never returned
            # to the pool.
            try:
                db.close()
            except Exception:
                pass

        if not found_job:
            return

        # run_one_queued_job() opens its own session internally
        # (matching the existing pattern in job_runner.py), so this
        # deliberately doesn't reuse the lookup session above.
        run_db = self.db_session_factory()
        try:
            run_one_queued_job(run_db, tenant_id, universe_id)
        except Exception:
            logger.exception("Job queue runner: a queued job run failed")
        finally:
            try:
                run_db.close()
            except Exception:
                pass


_RUNNER: Optional[JobQueueRunnerService] = None


def get_job_queue_runner_service(
    db_session_factory=None,
) -> Optional[JobQueueRunnerService]:
    global _RUNNER
    if _RUNNER is None and db_session_factory is not None:
        _RUNNER = JobQueueRunnerService(db_session_factory)
    return _RUNNER


def ensure_job_queue_runner_started(db_session_factory) -> None:
    """
    Idempotent auto-start entry point -- safe to call on every app
    load. start() itself is already a no-op if already running, so
    calling this repeatedly (once per user session that loads the
    app) is safe and does not spawn duplicate threads.
    """
    runner = get_job_queue_runner_service(db_session_factory)
    if runner is not None and not runner.running:
        runner.start()