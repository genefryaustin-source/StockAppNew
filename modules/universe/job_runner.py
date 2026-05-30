from __future__ import annotations

from typing import Optional
from sqlalchemy.orm import Session

from modules.jobs.models import Job
from modules.jobs.service import (
    start_job,
    succeed_job,
    fail_job,
    append_log,
    set_progress,
    parse_payload,
)

from modules.universe.batch_engine import refresh_universe_cache


def run_one_queued_job(db: Session, tenant_id: str, universe_id: str = None):
    """
    Executes ONE queued job for the tenant (optionally filtered by universe)
    """

    q = db.query(Job).filter(
        Job.tenant_id == tenant_id,
        Job.status == "queued",
    )

    # 🔥 CRITICAL FIX
    if universe_id:
        q = q.filter(Job.universe_id == universe_id)

    q = db.query(Job).filter(
        Job.tenant_id == tenant_id,
        Job.status == "queued",
    )

    # 🔥 CRITICAL FIX
    if universe_id:
        q = q.filter(Job.universe_id == universe_id)

    job = q.order_by(Job.created_at.asc()).first()

    if not job:
        print("⚠️ No matching queued jobs found")
        return None

    print(f"🚀 Running job {job.id} (universe={job.universe_id})")

    try:
        start_job(db, job)
        append_log(db, job, f"Started job {job.id}")

        payload = parse_payload(job)

        if job.job_type == "universe_refresh":

            universe_id = payload.get("universe_id") or job.universe_id

            if not universe_id:
                raise Exception("Missing universe_id")

            def progress(done: int, total: int, symbol: str):
                try:
                    set_progress(db, job, done + 1, total)
                    append_log(db, job, f"{done+1}/{total} {symbol}")
                except Exception:
                    pass

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

        else:
            raise Exception(f"Unknown job_type: {job.job_type}")

        succeed_job(db, job)
        append_log(db, job, "Job completed successfully.")

        return job.id

    except Exception as e:
        fail_job(db, job, str(e))
        append_log(db, job, f"Job failed: {e}")
        return job.id


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
