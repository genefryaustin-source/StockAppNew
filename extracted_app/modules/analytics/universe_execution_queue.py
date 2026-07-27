"""
modules/analytics/universe_execution_queue.py

Optimized Analytics Universe Execution Queue.

Fixes:
- Optional profiler support.
- PRAGMA journal_mode is set during initialization, not per operation.
- Adds enqueue_jobs_bulk() and claim_jobs() batch-compatible methods.
- Preserves existing public APIs used by runtime and tests.
"""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from modules.analytics.universe_job_registry import UniverseJobRegistry, UniverseJobStatus

DEFAULT_DB_PATH = "data/analytics_fabric.db"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def ensure_parent(path_str: str) -> None:
    path = Path(path_str)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class QueueLease:
    lease_id: str
    job_id: str
    tenant_id: str
    worker_id: str
    lease_expires_at: str
    heartbeat_at: str
    claimed_at: str


class UniverseExecutionQueue:
    """Durable analytics execution queue."""

    PRIORITY_ORDER = {
        "CRITICAL": 1,
        "HIGH": 2,
        "NORMAL": 3,
        "LOW": 4,
    }

    def __init__(
        self,
        registry: UniverseJobRegistry,
        db_path: str = DEFAULT_DB_PATH,
        default_lease_seconds: int = 300,
        profiler: Optional[Any] = None,
    ) -> None:
        self.registry = registry
        self.db_path = db_path
        self.default_lease_seconds = int(default_lease_seconds)
        self.profiler = profiler
        self._lock = threading.RLock()
        ensure_parent(self.db_path)
        self.initialize()

    def _record(self, method_name: str, *args: Any) -> None:
        if self.profiler is None:
            return
        method = getattr(self.profiler, method_name, None)
        if callable(method):
            try:
                method(*args)
            except Exception:
                pass

    def _execute(self, conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()): 
        start = time.perf_counter()
        result = conn.execute(sql, tuple(params))
        self._record("record_execute", (time.perf_counter() - start) * 1000)
        return result

    def _executemany(self, conn: sqlite3.Connection, sql: str, rows: Iterable[Iterable[Any]]):
        rows_list = list(rows)
        start = time.perf_counter()
        result = conn.executemany(sql, rows_list)
        self._record("record_executemany", (time.perf_counter() - start) * 1000)
        return result

    @contextmanager
    def _connect(self):
        start = time.perf_counter()
        conn = sqlite3.connect(self.db_path, timeout=30)
        self._record("record_connection_open", (time.perf_counter() - start) * 1000)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            start = time.perf_counter()
            conn.commit()
            self._record("record_commit", (time.perf_counter() - start) * 1000)
        except Exception:
            try:
                conn.rollback()
                self._record("record_rollback")
            finally:
                raise
        finally:
            start = time.perf_counter()
            conn.close()
            self._record("record_connection_close", (time.perf_counter() - start) * 1000)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA temp_store = MEMORY")
            conn.execute("PRAGMA cache_size = -20000")
            self._execute(conn, """
                CREATE TABLE IF NOT EXISTS universe_execution_queue (
                    queue_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    priority_rank INTEGER NOT NULL,
                    queued_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    claimed INTEGER NOT NULL DEFAULT 0,
                    claimed_by TEXT,
                    claimed_at TEXT,
                    UNIQUE(job_id)
                )
            """)
            self._execute(conn, """
                CREATE TABLE IF NOT EXISTS universe_job_leases (
                    lease_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    claimed_at TEXT NOT NULL,
                    heartbeat_at TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    UNIQUE(job_id)
                )
            """)
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_analytics_queue_available ON universe_execution_queue (claimed, priority_rank, available_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_analytics_queue_tenant ON universe_execution_queue (tenant_id, claimed, priority_rank, queued_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_analytics_leases_expiry ON universe_job_leases (lease_expires_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_analytics_leases_worker ON universe_job_leases (worker_id, lease_expires_at)")

    def enqueue_job(self, tenant_id: str, job_id: str, priority: str = "NORMAL", delay_seconds: int = 0) -> bool:
        priority_rank = self.PRIORITY_ORDER.get(priority.upper(), self.PRIORITY_ORDER["NORMAL"])
        now = utc_now()
        available_at = now + timedelta(seconds=int(delay_seconds))
        with self._lock:
            with self._connect() as conn:
                exists = self._execute(conn, "SELECT job_id FROM universe_execution_queue WHERE job_id = ?", (job_id,)).fetchone()
                if exists:
                    return False
                self._execute(conn, self._insert_queue_sql(), (f"uq_{uuid.uuid4().hex}", tenant_id, job_id, priority_rank, now.isoformat(), available_at.isoformat(), 0, None, None))
        self.registry.mark_queued(tenant_id=tenant_id, job_id=job_id)
        return True

    def enqueue_jobs_bulk(self, *, jobs: Iterable[tuple[str, str, str]], delay_seconds: int = 0, mark_registry_queued: bool = True) -> int:
        rows_input = list(jobs)
        if not rows_input:
            return 0
        now = utc_now()
        available_at = now + timedelta(seconds=int(delay_seconds))
        rows = [
            (
                f"uq_{uuid.uuid4().hex}", tenant_id, job_id,
                self.PRIORITY_ORDER.get(str(priority).upper(), self.PRIORITY_ORDER["NORMAL"]),
                now.isoformat(), available_at.isoformat(), 0, None, None,
            )
            for tenant_id, job_id, priority in rows_input
        ]
        with self._lock:
            with self._connect() as conn:
                before = conn.total_changes
                self._executemany(conn, self._insert_queue_sql(insert_or_ignore=True), rows)
                inserted = conn.total_changes - before
        if mark_registry_queued and inserted > 0:
            by_tenant: Dict[str, List[str]] = {}
            for tenant_id, job_id, _priority in rows_input:
                by_tenant.setdefault(tenant_id, []).append(job_id)
            for tenant_id, job_ids in by_tenant.items():
                bulk_update = getattr(self.registry, "update_status_bulk", None)
                if callable(bulk_update):
                    bulk_update(tenant_id=tenant_id, job_ids=job_ids, status=UniverseJobStatus.QUEUED, event_type="JOB_QUEUED", message="Universe analytics job queued.")
                else:
                    for job_id in job_ids:
                        self.registry.mark_queued(tenant_id=tenant_id, job_id=job_id)
        return int(inserted)

    def claim_next_job(self, worker_id: str, lease_seconds: Optional[int] = None) -> Optional[QueueLease]:
        claims = self.claim_jobs(worker_id=worker_id, limit=1, lease_seconds=lease_seconds)
        return claims[0] if claims else None

    def claim_jobs(self, worker_id: str, limit: int = 1, lease_seconds: Optional[int] = None) -> List[QueueLease]:
        lease_seconds = int(lease_seconds or self.default_lease_seconds)
        limit = max(1, int(limit))
        leases: List[QueueLease] = []
        now = utc_now()
        expires = now + timedelta(seconds=lease_seconds)
        with self._lock:
            with self._connect() as conn:
                rows = self._execute(conn, """
                    SELECT * FROM universe_execution_queue
                    WHERE claimed = 0 AND available_at <= ?
                    ORDER BY priority_rank ASC, queued_at ASC
                    LIMIT ?
                """, (now.isoformat(), limit)).fetchall()
                if not rows:
                    return []
                for row in rows:
                    lease = QueueLease(
                        lease_id=f"lease_{uuid.uuid4().hex}", tenant_id=row["tenant_id"], job_id=row["job_id"],
                        worker_id=worker_id, claimed_at=now.isoformat(), heartbeat_at=now.isoformat(),
                        lease_expires_at=expires.isoformat(),
                    )
                    self._execute(conn, "UPDATE universe_execution_queue SET claimed = 1, claimed_by = ?, claimed_at = ? WHERE job_id = ? AND claimed = 0", (worker_id, now.isoformat(), lease.job_id))
                    self._execute(conn, """
                        INSERT INTO universe_job_leases (lease_id, tenant_id, job_id, worker_id, claimed_at, heartbeat_at, lease_expires_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (lease.lease_id, lease.tenant_id, lease.job_id, lease.worker_id, lease.claimed_at, lease.heartbeat_at, lease.lease_expires_at))
                    leases.append(lease)
        by_tenant: Dict[str, List[str]] = {}
        for lease in leases:
            by_tenant.setdefault(lease.tenant_id, []).append(lease.job_id)
        for tenant_id, job_ids in by_tenant.items():
            bulk_update = getattr(self.registry, "update_status_bulk", None)
            if callable(bulk_update):
                bulk_update(tenant_id=tenant_id, job_ids=job_ids, status=UniverseJobStatus.RUNNING, event_type="JOB_RUNNING", message="Universe analytics job started.")
            else:
                for job_id in job_ids:
                    self.registry.mark_running(tenant_id=tenant_id, job_id=job_id)
        return leases

    def heartbeat(self, lease_id: str, extend_seconds: Optional[int] = None) -> bool:
        extend_seconds = int(extend_seconds or self.default_lease_seconds)
        now = utc_now()
        with self._connect() as conn:
            row = self._execute(conn, "SELECT * FROM universe_job_leases WHERE lease_id = ?", (lease_id,)).fetchone()
            if not row:
                return False
            self._execute(conn, "UPDATE universe_job_leases SET heartbeat_at = ?, lease_expires_at = ? WHERE lease_id = ?", (now.isoformat(), (now + timedelta(seconds=extend_seconds)).isoformat(), lease_id))
        return True

    def complete_job(self, lease_id: str, result_ref: Optional[str] = None) -> bool:
        with self._lock:
            with self._connect() as conn:
                lease = self._execute(conn, "SELECT * FROM universe_job_leases WHERE lease_id = ?", (lease_id,)).fetchone()
                if not lease:
                    return False
                tenant_id = lease["tenant_id"]
                job_id = lease["job_id"]
                self._execute(conn, "DELETE FROM universe_job_leases WHERE lease_id = ?", (lease_id,))
                self._execute(conn, "DELETE FROM universe_execution_queue WHERE job_id = ?", (job_id,))
        self.registry.mark_completed(tenant_id=tenant_id, job_id=job_id, result_ref=result_ref)
        return True

    def complete_jobs_bulk(self, lease_ids: Sequence[str], result_ref_prefix: str = "bulk_result") -> int:
        completed = 0
        for lease_id in lease_ids:
            if self.complete_job(lease_id=lease_id, result_ref=f"{result_ref_prefix}_{lease_id}"):
                completed += 1
        return completed

    def fail_job(self, lease_id: str, error_message: str, retry_delay_seconds: int = 60) -> bool:
        with self._lock:
            with self._connect() as conn:
                lease = self._execute(conn, "SELECT * FROM universe_job_leases WHERE lease_id = ?", (lease_id,)).fetchone()
                if not lease:
                    return False
                tenant_id = lease["tenant_id"]
                job_id = lease["job_id"]
                self._execute(conn, "DELETE FROM universe_job_leases WHERE lease_id = ?", (lease_id,))
                self._execute(conn, """
                    UPDATE universe_execution_queue
                    SET claimed = 0, claimed_by = NULL, claimed_at = NULL, available_at = ?
                    WHERE job_id = ?
                """, ((utc_now() + timedelta(seconds=int(retry_delay_seconds))).isoformat(), job_id))
        self.registry.mark_failed(tenant_id=tenant_id, job_id=job_id, error_message=error_message, retry_pending=True)
        return True

    def recover_expired_leases(self) -> int:
        recovered = 0
        with self._lock:
            with self._connect() as conn:
                expired = self._execute(conn, "SELECT * FROM universe_job_leases WHERE lease_expires_at < ?", (utc_now_iso(),)).fetchall()
                for lease in expired:
                    job_id = lease["job_id"]
                    self._execute(conn, "DELETE FROM universe_job_leases WHERE lease_id = ?", (lease["lease_id"],))
                    self._execute(conn, """
                        UPDATE universe_execution_queue
                        SET claimed = 0, claimed_by = NULL, claimed_at = NULL
                        WHERE job_id = ?
                    """, (job_id,))
                    recovered += 1
        return recovered

    def queue_depth(self) -> int:
        with self._connect() as conn:
            row = self._execute(conn, "SELECT COUNT(*) AS cnt FROM universe_execution_queue").fetchone()
        return int(row["cnt"])

    def active_leases(self) -> int:
        with self._connect() as conn:
            row = self._execute(conn, "SELECT COUNT(*) AS cnt FROM universe_job_leases").fetchone()
        return int(row["cnt"])

    def queue_metrics(self) -> Dict[str, Any]:
        with self._connect() as conn:
            depth = self._execute(conn, "SELECT COUNT(*) AS cnt FROM universe_execution_queue").fetchone()["cnt"]
            active = self._execute(conn, "SELECT COUNT(*) AS cnt FROM universe_job_leases").fetchone()["cnt"]
            unclaimed = self._execute(conn, "SELECT COUNT(*) AS cnt FROM universe_execution_queue WHERE claimed = 0").fetchone()["cnt"]
        return {"queue_depth": int(depth), "active_leases": int(active), "unclaimed_jobs": int(unclaimed), "generated_at": utc_now_iso()}

    def get_active_leases(self) -> List[QueueLease]:
        with self._connect() as conn:
            rows = self._execute(conn, "SELECT * FROM universe_job_leases ORDER BY claimed_at ASC").fetchall()
        return [QueueLease(lease_id=r["lease_id"], tenant_id=r["tenant_id"], job_id=r["job_id"], worker_id=r["worker_id"], claimed_at=r["claimed_at"], heartbeat_at=r["heartbeat_at"], lease_expires_at=r["lease_expires_at"]) for r in rows]

    @staticmethod
    def _insert_queue_sql(insert_or_ignore: bool = False) -> str:
        verb = "INSERT OR IGNORE" if insert_or_ignore else "INSERT"
        return f"""
            {verb} INTO universe_execution_queue (
                queue_id, tenant_id, job_id, priority_rank, queued_at, available_at, claimed, claimed_by, claimed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """


def create_universe_execution_queue(*, registry: UniverseJobRegistry, db_path: str = DEFAULT_DB_PATH, default_lease_seconds: int = 300, profiler: Optional[Any] = None) -> UniverseExecutionQueue:
    return UniverseExecutionQueue(registry=registry, db_path=db_path, default_lease_seconds=default_lease_seconds, profiler=profiler)
