from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from modules.db.core import SessionLocal
from modules.db.connection_resilience import (
    is_dead_connection_error,
    get_fresh_session,
)
from modules.jobs.models import Job
from modules.jobs.service import (
    start_job,
    succeed_job,
    fail_job,
    append_log,
    set_progress,
    parse_payload,
    enqueue_job,
)

from modules.universe.batch_engine import refresh_universe_cache


def run_one_queued_job(db: Session, tenant_id: str, universe_id: str = None):
    """
    Executes ONE queued job for the tenant (optionally filtered by universe)
    """



    # 🔥 CRITICAL FIX
    q = db.query(Job).filter(
        Job.tenant_id == tenant_id,
        Job.status == "queued",
    )

    if universe_id:
        q = q.filter(Job.universe_id == universe_id)



    # 🔥 CRITICAL FIX
    if universe_id:
        q = q.filter(Job.universe_id == universe_id)

    job = q.order_by(Job.created_at.asc()).first()

    if not job:
        print("⚠️ No matching queued jobs found")
        return None

    # Captured now, while the session is healthy -- every subsequent
    # error-handling branch below uses these plain values instead of
    # re-accessing job.id/job.universe_id, which risk triggering a
    # lazy-load query on what may later be a poisoned, needs-rollback
    # session and turning a log statement into a second crash.
    job_id = job.id
    job_universe_id = job.universe_id

    print(f"🚀 Running job {job_id} (universe={job_universe_id})")

    try:
        start_job(db, job)
        append_log(db, job, f"Started job {job_id}")

        payload = parse_payload(job)

        if job.job_type == "universe_refresh":

            universe_id = payload.get("universe_id") or job_universe_id

            if not universe_id:
                raise Exception("Missing universe_id")

            def progress(done: int, total: int, symbol: str):

                progress_db = SessionLocal()

                try:

                    progress_job = (
                        progress_db.query(Job)
                        .filter(Job.id == job_id)
                        .first()
                    )

                    if progress_job is None:
                        return

                    set_progress(
                        progress_db,
                        progress_job,
                        done + 1,
                        total,
                    )

                    append_log(
                        progress_db,
                        progress_job,
                        f"{done + 1}/{total} {symbol}",
                    )

                    progress_db.commit()

                except Exception as e:

                    print("Progress update error:", e)

                    progress_db.rollback()

                finally:

                    progress_db.close()

            print(
                "🚨 STEP 1 — BEFORE refresh_universe_cache"
            )

            append_log(
                db,
                job,
                "🚨 STEP 1 — BEFORE refresh_universe_cache"
            )

            result = refresh_universe_cache(
                db=db,
                tenant_id=tenant_id,
                universe_id=universe_id,
                progress=progress,
            )

            # Pick up whatever session refresh_universe_cache() ended up
            # using -- if a mid-loop reconnection happened inside it
            # (runner.py's own per-symbol recovery), that fix was scoped
            # to a local variable inside that call chain and never
            # reached this outer `db` on its own.
            db = result.get("_db", db)

            # The refresh above can run for many minutes across thousands
            # of symbols -- this `db` session has been checked out the
            # whole time, which is exactly the situation Neon's
            # serverless idle-connection cutoff tends to kill mid-job.
            # The _db propagation above only covers a session that was
            # already healed inside runner.py's own loop; it doesn't
            # cover a connection that died in the gap *after* the last
            # per-symbol operation but before this point. A real query
            # is needed to actually detect that -- expire_all() is a
            # purely in-memory operation that never issues any SQL, so
            # it can never actually observe a dead connection.
            try:
                db.execute(text("SELECT 1"))
            except Exception as e:
                if not is_dead_connection_error(e):
                    raise
                print(f"⚠️ Job session dropped after refresh_universe_cache -- reconnecting: {e}")
                try:
                    db.rollback()
                except Exception:
                    pass
                try:
                    db.close()
                except Exception:
                    pass
                db = get_fresh_session()
                # `job` is an ORM object bound to the now-closed session --
                # re-fetch it against the new one rather than risk a
                # DetachedInstanceError on its next attribute access. Uses
                # the job_id captured at the top of this function, not
                # job.id itself, since that attribute access is exactly
                # the kind of thing that risks failing on the old session.
                job = db.query(Job).filter(Job.id == job_id).first()
                if job is None:
                    raise Exception(
                        "Job row disappeared after reconnecting -- cannot finalize."
                    )

            print(
                "🚨 STEP 2 — AFTER refresh_universe_cache"
            )

            append_log(
                db,
                job,
                "🚨 STEP 2 — AFTER refresh_universe_cache"
            )

            print("REFRESH RESULT:", result)

            append_log(db, job, f"Refresh result: {result}")

            stale_remaining = int(result.get("stale_or_missing", 0) or 0)
            made_progress = int(result.get("ran_analytics", 0) or 0) > 0

            if stale_remaining > 0 and made_progress:
                enqueue_job(
                    db=db,
                    tenant_id=tenant_id,
                    job_type="universe_refresh",
                    universe_id=universe_id,
                    payload=payload,
                )
                append_log(
                    db,
                    job,
                    f"Auto-queued follow-up batch -- {stale_remaining} symbols still stale.",
                )
                print(f"🔁 AUTO-QUEUED FOLLOW-UP BATCH: {stale_remaining} symbols still stale")

            elif stale_remaining > 0 and not made_progress:
                append_log(
                    db,
                    job,
                    f"NOT auto-queuing a follow-up batch: this run made zero progress "
                    f"({stale_remaining} symbols still stale). Likely a provider outage "
                    f"or a genuinely stuck subset of symbols -- needs manual review before "
                    f"retrying automatically.",
                )
                print(f"⚠️ NOT auto-queuing follow-up: zero progress this run, {stale_remaining} still stale")

        else:
            raise Exception(f"Unknown job_type: {job.job_type}")

        try:
            db.rollback()
        except Exception:
            pass

        succeed_job(db, job)
        append_log(db, job, "Job completed successfully.")

        return job_id

    except Exception as e:
        # `db` might also be the dead one if we got here some other way
        # (or if the reconnect above itself failed) -- without this, the
        # job would get stuck showing "running" forever instead of being
        # correctly marked failed, since fail_job() itself would silently
        # fail too.
        try:
            # Critical: if the original exception left this session
            # needing a rollback (which any failed flush/commit does),
            # fail_job() below is guaranteed to fail immediately without
            # this -- SQLAlchemy refuses any further operation on a
            # session until it's explicitly rolled back first.
            try:
                db.rollback()
            except Exception:
                pass
            fail_job(db, job, str(e))
            append_log(db, job, f"Job failed: {e}")
        except Exception as e2:
            if is_dead_connection_error(e2):
                try:
                    db2 = get_fresh_session()
                    job2 = db2.query(Job).filter(Job.id == job_id).first()
                    if job2 is not None:
                        fail_job(db2, job2, str(e))
                        append_log(db2, job2, f"Job failed: {e}")
                    db2.close()
                except Exception as e3:
                    print(f"⚠️ Could not mark job {job_id} as failed even after reconnecting: {e3}")
            else:
                print(f"⚠️ Could not mark job {job_id} as failed: {e2}")
        return job_id


def run_specific_job(db, job_id: str):
    """
    Runs a specific job by ID (bypasses queue filtering issues)
    """

    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        print(f"❌ Job not found: {job_id}")
        return None

    print(f"🚀 Running specific job {job.id}")

    return run_one_queued_job(
        db,
        job.tenant_id,
        job.universe_id
    )