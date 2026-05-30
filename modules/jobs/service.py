import json
from datetime import datetime, UTC
from typing import Optional, Any

from sqlalchemy.orm import Session

from modules.db.models import gen_uuid
from modules.jobs.models import Job
from modules.universe.batch_engine import refresh_universe_cache


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------
# Basic job helpers
# ---------------------------------------------------

def parse_payload(job: Job) -> dict[str, Any]:
    try:
        return json.loads(job.payload) if job.payload else {}
    except Exception:
        return {}


def append_job_log(db: Session, job: Job, line: str):
    existing = job.logs or ""
    job.logs = existing + line.rstrip() + "\n"
    db.commit()


# alias used by other modules
append_log = append_job_log


def set_job_progress(db: Session, job: Job, done: int, total: Optional[int] = None):
    job.done = int(done)
    if total is not None:
        job.total = int(total)
    db.commit()


# alias used by other modules
set_progress = set_job_progress


def start_job(db: Session, job: Job):
    job.status = "running"
    job.started_at = _now_iso()
    job.finished_at = None
    job.error = None
    db.commit()


def succeed_job(db: Session, job: Job):
    job.status = "succeeded"
    job.finished_at = _now_iso()
    db.commit()


def fail_job(db: Session, job: Job, error: str):
    job.status = "failed"
    job.error = str(error)
    job.finished_at = _now_iso()
    db.commit()


# ---------------------------------------------------
# List jobs
# ---------------------------------------------------

def list_jobs(db: Session, tenant_id: str, universe_id: str | None = None):
    q = db.query(Job).filter(Job.tenant_id == tenant_id)

    if universe_id:
        q = q.filter(Job.universe_id == universe_id)

    return q.order_by(Job.created_at.desc()).limit(100).all()


# ---------------------------------------------------
# Enqueue job
# ---------------------------------------------------

def enqueue_job(
    db: Session,
    tenant_id: str,
    job_type: str,
    universe_id: str | None = None,
    payload: dict | None = None,
):
    job = Job(
        id=gen_uuid(),
        tenant_id=tenant_id,
        job_type=job_type,
        status="queued",
        universe_id=universe_id,
        symbol=None,
        total=None,
        done=0,
        payload=json.dumps(payload) if payload else None,
        logs="",
        error=None,
        created_at=_now_iso(),
        started_at=None,
        finished_at=None,
    )

    db.add(job)
    db.commit()
    return job.id
    db.expire_all()

# ---------------------------------------------------
# Cancel / stop / dequeue / requeue
# ---------------------------------------------------

def cancel_job(db: Session, job_id: str):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    if job.status in ["succeeded", "failed", "cancelled", "stopped"]:
        return False
    job.status = "cancelled"
    job.finished_at = _now_iso()
    db.commit()
    return True


def stop_job(db: Session, job_id: str):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    if job.status != "running":
        return False
    job.status = "stopped"
    job.finished_at = _now_iso()
    db.commit()
    return True


def dequeue_job(db: Session, job_id: str):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    if job.status != "queued":
        return False
    db.delete(job)
    db.commit()
    return True


def requeue_job(db: Session, job_id: str):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False
    if job.status not in ["failed", "cancelled", "stopped"]:
        return False

    new_job = Job(
        id=gen_uuid(),
        tenant_id=job.tenant_id,
        job_type=job.job_type,
        status="queued",
        universe_id=job.universe_id,
        symbol=job.symbol,
        total=None,
        done=0,
        payload=job.payload,
        logs="",
        error=None,
        created_at=_now_iso(),
        started_at=None,
        finished_at=None,
    )
    db.add(new_job)
    db.commit()
    return new_job.id


# ---------------------------------------------------
# Single-job lock
# ---------------------------------------------------

def has_running_universe_refresh(db: Session, tenant_id: str):
    running = (
        db.query(Job)
        .filter(
            Job.tenant_id == tenant_id,
            Job.job_type == "universe_refresh",
            Job.status == "running",
        )
        .first()
    )
    return running is not None


# ---------------------------------------------------
# Run next queued job
# ---------------------------------------------------

def run_one_queued_job(db: Session, tenant_id: str):

    if has_running_universe_refresh(db, tenant_id):
        return None

    db.expire_all()   # force fresh DB read

    job = (
        db.query(Job)
        .filter(
            Job.tenant_id == tenant_id,
            Job.status == "queued",
        )
        .order_by(Job.created_at.asc())
        .first()
    )
        

    if not job:
        return None

    try:
        start_job(db, job)
        append_job_log(db, job, f"Started job type={job.job_type} id={job.id}")

        payload = parse_payload(job)

        if job.job_type == "universe_refresh":

            universe_id = payload.get("universe_id") or job.universe_id
            max_age_hours = int(payload.get("max_age_hours", 72))
            batch_size = int(payload.get("batch_size", 25))

            # new parallel controls
            parallel = bool(payload.get("parallel", True))
            max_workers = int(payload.get("max_workers", 12))

            if not universe_id:
                raise Exception("Missing universe_id")

            def progress(done: int, total: int, symbol: str):
                try:
                    set_job_progress(db, job, done, total)
                    append_job_log(db, job, f"{done}/{total} {symbol}")
                    db.refresh(job)
                    if job.status in ["cancelled", "stopped"]:
                        raise RuntimeError(f"Job interrupted at {symbol}")
                except RuntimeError:
                    raise
                except Exception:
                    pass

            result = refresh_universe_cache(
                db=db,
                tenant_id=tenant_id,
                universe_id=universe_id,
                max_age_hours=max_age_hours,
                batch_size=batch_size,
                progress=progress,
                parallel=parallel,
                max_workers=max_workers,
            )

            append_job_log(db, job, f"Refresh result: {result}")
            succeed_job(db, job)
            append_job_log(db, job, "Universe refresh complete.")
            from modules.core.cache_invalidation import (
                invalidate_all_app_caches,
            )

            #invalidate_all_app_caches()
            return job.id

        else:
            raise Exception(f"Unknown job_type: {job.job_type}")

    except Exception as e:
        fail_job(db, job, str(e))
        append_job_log(db, job, f"Job failed: {e}")
        return job.id
