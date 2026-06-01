"""
modules/analytics/universe_job_registry.py

Optimized Analytics Universe Job Registry.

Fixes:
- Optional profiler support; no AttributeError when profiler is absent.
- PRAGMA journal_mode is set during initialization, not on every operation.
- Short-lived SQLite connections are preserved.
- Bulk job registration and bulk status update paths added for high-volume loads.
- Existing public API is preserved.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DEFAULT_DB_PATH = "data/analytics_fabric.db"


class UniverseJobStatus(str, Enum):
    REGISTERED = "REGISTERED"
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PAUSED = "PAUSED"
    RETRY_PENDING = "RETRY_PENDING"


class UniverseJobPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class UniverseJobType(str, Enum):
    FUNDAMENTALS = "FUNDAMENTALS"
    TECHNICALS = "TECHNICALS"
    RANKING = "RANKING"
    SCREENING = "SCREENING"
    PORTFOLIO_ANALYTICS = "PORTFOLIO_ANALYTICS"
    UNIVERSE_REFRESH = "UNIVERSE_REFRESH"
    BACKTEST = "BACKTEST"
    SIGNAL_GENERATION = "SIGNAL_GENERATION"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    CUSTOM = "CUSTOM"


@dataclass(frozen=True)
class UniverseJob:
    job_id: str
    tenant_id: str
    universe_id: str
    job_type: str
    status: str = UniverseJobStatus.REGISTERED.value
    priority: str = UniverseJobPriority.NORMAL.value
    provider: Optional[str] = None
    symbol: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    result_ref: Optional[str] = None
    error_message: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    created_by: str = "system"
    created_at: str = field(default_factory=lambda: utc_now_iso())
    updated_at: str = field(default_factory=lambda: utc_now_iso())
    queued_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    cancelled_at: Optional[str] = None
    correlation_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class UniverseJobEvent:
    event_id: str
    job_id: str
    tenant_id: str
    event_type: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: utc_now_iso())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, default=str)


def _json_loads(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _ensure_parent_dir(db_path: str) -> None:
    path = Path(db_path)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)


def _normalize_status(status: str | UniverseJobStatus) -> str:
    return status.value if isinstance(status, UniverseJobStatus) else str(status).upper()


def _normalize_priority(priority: str | UniverseJobPriority) -> str:
    return priority.value if isinstance(priority, UniverseJobPriority) else str(priority).upper()


def _normalize_job_type(job_type: str | UniverseJobType) -> str:
    return job_type.value if isinstance(job_type, UniverseJobType) else str(job_type).upper()


class UniverseJobRegistry:
    """Durable registry for analytics universe jobs."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, profiler: Optional[Any] = None) -> None:
        self.db_path = db_path
        self.profiler = profiler
        _ensure_parent_dir(self.db_path)
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
                CREATE TABLE IF NOT EXISTS universe_jobs (
                    job_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    universe_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    provider TEXT,
                    symbol TEXT,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    result_ref TEXT,
                    error_message TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    created_by TEXT NOT NULL DEFAULT 'system',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    queued_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    cancelled_at TEXT,
                    correlation_id TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]'
                )
            """)
            self._execute(conn, """
                CREATE TABLE IF NOT EXISTS universe_job_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES universe_jobs(job_id) ON DELETE CASCADE
                )
            """)
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_universe_jobs_tenant_status ON universe_jobs (tenant_id, status)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_universe_jobs_tenant_universe ON universe_jobs (tenant_id, universe_id)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_universe_jobs_priority_created ON universe_jobs (priority, created_at)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_universe_jobs_symbol ON universe_jobs (tenant_id, symbol)")
            self._execute(conn, "CREATE INDEX IF NOT EXISTS idx_universe_job_events_job ON universe_job_events (job_id, created_at)")

    def register_job(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        job_type: str | UniverseJobType,
        priority: str | UniverseJobPriority = UniverseJobPriority.NORMAL,
        provider: Optional[str] = None,
        symbol: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
        created_by: str = "system",
        correlation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        job_id: Optional[str] = None,
    ) -> UniverseJob:
        now = utc_now_iso()
        normalized_job = UniverseJob(
            job_id=job_id or f"ujob_{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            universe_id=universe_id,
            job_type=_normalize_job_type(job_type),
            status=UniverseJobStatus.REGISTERED.value,
            priority=_normalize_priority(priority),
            provider=provider,
            symbol=symbol,
            payload=payload or {},
            max_attempts=max(1, int(max_attempts)),
            created_by=created_by,
            created_at=now,
            updated_at=now,
            correlation_id=correlation_id,
            tags=tags or [],
        )
        with self._connect() as conn:
            self._insert_job_conn(conn, normalized_job)
            self._insert_event_conn(conn, job_id=normalized_job.job_id, tenant_id=tenant_id, event_type="JOB_REGISTERED", message="Universe analytics job registered.", payload=asdict(normalized_job))
        return normalized_job

    def register_bulk_jobs(
        self,
        *,
        tenant_id: str,
        universe_id: str,
        job_type: str | UniverseJobType,
        symbols: Iterable[str],
        priority: str | UniverseJobPriority = UniverseJobPriority.NORMAL,
        provider: Optional[str] = None,
        base_payload: Optional[Dict[str, Any]] = None,
        max_attempts: int = 3,
        created_by: str = "system",
        correlation_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[UniverseJob]:
        now = utc_now_iso()
        jobs: List[UniverseJob] = []
        for symbol in symbols:
            payload = dict(base_payload or {})
            payload["symbol"] = symbol
            jobs.append(UniverseJob(
                job_id=f"ujob_{uuid.uuid4().hex}", tenant_id=tenant_id, universe_id=universe_id,
                job_type=_normalize_job_type(job_type), status=UniverseJobStatus.REGISTERED.value,
                priority=_normalize_priority(priority), provider=provider, symbol=symbol, payload=payload,
                max_attempts=max(1, int(max_attempts)), created_by=created_by, created_at=now,
                updated_at=now, correlation_id=correlation_id, tags=tags or []
            ))
        if not jobs:
            return []
        with self._connect() as conn:
            self._executemany(conn, self._insert_job_sql(), [self._job_insert_tuple(job) for job in jobs])
            self._executemany(conn, self._insert_event_sql(), [
                (f"ujevt_{uuid.uuid4().hex}", job.job_id, tenant_id, "JOB_REGISTERED", "Universe analytics job registered.", _json_dumps(asdict(job)), utc_now_iso())
                for job in jobs
            ])
        return jobs

    def register_jobs_bulk(self, *args: Any, **kwargs: Any) -> List[UniverseJob]:
        return self.register_bulk_jobs(*args, **kwargs)

    def get_job(self, *, tenant_id: str, job_id: str) -> Optional[UniverseJob]:
        with self._connect() as conn:
            row = self._execute(conn, "SELECT * FROM universe_jobs WHERE tenant_id = ? AND job_id = ?", (tenant_id, job_id)).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(
        self,
        *,
        tenant_id: str,
        universe_id: Optional[str] = None,
        status: Optional[str | UniverseJobStatus] = None,
        job_type: Optional[str | UniverseJobType] = None,
        priority: Optional[str | UniverseJobPriority] = None,
        provider: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 250,
    ) -> List[UniverseJob]:
        clauses = ["tenant_id = ?"]
        params: List[Any] = [tenant_id]
        if universe_id:
            clauses.append("universe_id = ?"); params.append(universe_id)
        if status:
            clauses.append("status = ?"); params.append(_normalize_status(status))
        if job_type:
            clauses.append("job_type = ?"); params.append(_normalize_job_type(job_type))
        if priority:
            clauses.append("priority = ?"); params.append(_normalize_priority(priority))
        if provider:
            clauses.append("provider = ?"); params.append(provider)
        if symbol:
            clauses.append("symbol = ?"); params.append(symbol)
        params.append(max(1, int(limit)))
        query = f"SELECT * FROM universe_jobs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?"
        with self._connect() as conn:
            rows = self._execute(conn, query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_job_events(self, *, tenant_id: str, job_id: str, limit: int = 500) -> List[UniverseJobEvent]:
        with self._connect() as conn:
            rows = self._execute(conn, "SELECT * FROM universe_job_events WHERE tenant_id = ? AND job_id = ? ORDER BY created_at ASC LIMIT ?", (tenant_id, job_id, max(1, int(limit)))).fetchall()
        return [self._row_to_event(row) for row in rows]

    def mark_queued(self, *, tenant_id: str, job_id: str) -> Optional[UniverseJob]:
        return self.update_status(tenant_id=tenant_id, job_id=job_id, status=UniverseJobStatus.QUEUED, timestamp_field="queued_at", event_type="JOB_QUEUED", message="Universe analytics job queued.")

    def mark_running(self, *, tenant_id: str, job_id: str) -> Optional[UniverseJob]:
        return self.update_status(tenant_id=tenant_id, job_id=job_id, status=UniverseJobStatus.RUNNING, timestamp_field="started_at", increment_attempt=True, event_type="JOB_RUNNING", message="Universe analytics job started.")

    def mark_completed(self, *, tenant_id: str, job_id: str, result_ref: Optional[str] = None, payload: Optional[Dict[str, Any]] = None) -> Optional[UniverseJob]:
        now = utc_now_iso()
        with self._connect() as conn:
            row = self._execute(conn, """
                UPDATE universe_jobs SET status = ?, result_ref = COALESCE(?, result_ref), error_message = NULL, completed_at = ?, updated_at = ?
                WHERE tenant_id = ? AND job_id = ? RETURNING *
            """, (UniverseJobStatus.COMPLETED.value, result_ref, now, now, tenant_id, job_id)).fetchone()
            if row:
                self._insert_event_conn(conn, job_id=job_id, tenant_id=tenant_id, event_type="JOB_COMPLETED", message="Universe analytics job completed.", payload=payload or {"result_ref": result_ref})
        return self._row_to_job(row) if row else None

    def mark_failed(self, *, tenant_id: str, job_id: str, error_message: str, retry_pending: bool = True, payload: Optional[Dict[str, Any]] = None) -> Optional[UniverseJob]:
        existing = self.get_job(tenant_id=tenant_id, job_id=job_id)
        if not existing:
            return None
        can_retry = retry_pending and existing.attempt_count < existing.max_attempts
        next_status = UniverseJobStatus.RETRY_PENDING.value if can_retry else UniverseJobStatus.FAILED.value
        now = utc_now_iso()
        with self._connect() as conn:
            row = self._execute(conn, """
                UPDATE universe_jobs SET status = ?, error_message = ?, updated_at = ?
                WHERE tenant_id = ? AND job_id = ? RETURNING *
            """, (next_status, error_message, now, tenant_id, job_id)).fetchone()
            if row:
                self._insert_event_conn(conn, job_id=job_id, tenant_id=tenant_id, event_type="JOB_FAILED" if not can_retry else "JOB_RETRY_PENDING", message=error_message, payload=payload or {"error_message": error_message})
        return self._row_to_job(row) if row else None

    def cancel_job(self, *, tenant_id: str, job_id: str, reason: str = "Cancelled by request.") -> Optional[UniverseJob]:
        return self.update_status(tenant_id=tenant_id, job_id=job_id, status=UniverseJobStatus.CANCELLED, timestamp_field="cancelled_at", event_type="JOB_CANCELLED", message=reason, payload={"reason": reason})

    def pause_job(self, *, tenant_id: str, job_id: str, reason: str = "Paused by request.") -> Optional[UniverseJob]:
        return self.update_status(tenant_id=tenant_id, job_id=job_id, status=UniverseJobStatus.PAUSED, event_type="JOB_PAUSED", message=reason, payload={"reason": reason})

    def update_status(self, *, tenant_id: str, job_id: str, status: str | UniverseJobStatus, timestamp_field: Optional[str] = None, increment_attempt: bool = False, event_type: str = "JOB_STATUS_UPDATED", message: str = "Universe analytics job status updated.", payload: Optional[Dict[str, Any]] = None) -> Optional[UniverseJob]:
        allowed_timestamp_fields = {"queued_at", "started_at", "completed_at", "cancelled_at"}
        if timestamp_field and timestamp_field not in allowed_timestamp_fields:
            raise ValueError(f"Unsupported timestamp field: {timestamp_field}")
        now = utc_now_iso()
        normalized_status = _normalize_status(status)
        set_parts = ["status = ?", "updated_at = ?"]
        params: List[Any] = [normalized_status, now]
        if timestamp_field:
            set_parts.append(f"{timestamp_field} = ?"); params.append(now)
        if increment_attempt:
            set_parts.append("attempt_count = attempt_count + 1")
        params.extend([tenant_id, job_id])
        with self._connect() as conn:
            row = self._execute(conn, f"UPDATE universe_jobs SET {', '.join(set_parts)} WHERE tenant_id = ? AND job_id = ? RETURNING *", params).fetchone()
            if row:
                self._insert_event_conn(conn, job_id=job_id, tenant_id=tenant_id, event_type=event_type, message=message, payload=payload or {"status": normalized_status})
        return self._row_to_job(row) if row else None

    def update_status_bulk(
            self,
            *,
            tenant_id: str,
            job_ids: Iterable[str],
            status: str | UniverseJobStatus,
            event_type: str = "JOB_STATUS_UPDATED",
            message: str = "Universe analytics job status updated.",
    ) -> int:

        ids = list(job_ids)

        if not ids:
            return 0

        normalized_status = _normalize_status(status)

        now = utc_now_iso()

        updated_ids = []

        with self._connect() as conn:

            for job_id in ids:

                cursor = conn.execute(
                    """
                    UPDATE universe_jobs
                    SET status = ?,
                        updated_at = ?
                    WHERE tenant_id = ?
                    AND job_id = ?
                    """,
                    (
                        normalized_status,
                        now,
                        tenant_id,
                        job_id,
                    ),
                )

                if cursor.rowcount > 0:
                    updated_ids.append(job_id)

            if updated_ids:
                self._executemany(
                    conn,
                    self._insert_event_sql(),
                    [
                        (
                            f"ujevt_{uuid.uuid4().hex}",
                            job_id,
                            tenant_id,
                            event_type,
                            message,
                            _json_dumps(
                                {
                                    "status": normalized_status
                                }
                            ),
                            utc_now_iso(),
                        )
                        for job_id in updated_ids
                    ],
                )

        return len(updated_ids)

    def update_payload(self, *, tenant_id: str, job_id: str, patch: Dict[str, Any], merge: bool = True) -> Optional[UniverseJob]:
        existing = self.get_job(tenant_id=tenant_id, job_id=job_id)
        if not existing:
            return None
        new_payload = dict(existing.payload) if merge else {}
        new_payload.update(patch or {})
        now = utc_now_iso()
        with self._connect() as conn:
            row = self._execute(conn, "UPDATE universe_jobs SET payload_json = ?, updated_at = ? WHERE tenant_id = ? AND job_id = ? RETURNING *", (_json_dumps(new_payload), now, tenant_id, job_id)).fetchone()
            if row:
                self._insert_event_conn(conn, job_id=job_id, tenant_id=tenant_id, event_type="JOB_PAYLOAD_UPDATED", message="Universe analytics job payload updated.", payload={"patch": patch, "merge": merge})
        return self._row_to_job(row) if row else None

    def add_tags(self, *, tenant_id: str, job_id: str, tags: Iterable[str]) -> Optional[UniverseJob]:
        existing = self.get_job(tenant_id=tenant_id, job_id=job_id)
        if not existing:
            return None
        normalized_tags = sorted(set(existing.tags).union({str(t) for t in tags}))
        now = utc_now_iso()
        with self._connect() as conn:
            row = self._execute(conn, "UPDATE universe_jobs SET tags_json = ?, updated_at = ? WHERE tenant_id = ? AND job_id = ? RETURNING *", (_json_dumps(normalized_tags), now, tenant_id, job_id)).fetchone()
            if row:
                self._insert_event_conn(conn, job_id=job_id, tenant_id=tenant_id, event_type="JOB_TAGS_UPDATED", message="Universe analytics job tags updated.", payload={"tags": normalized_tags})
        return self._row_to_job(row) if row else None

    def delete_job(self, *, tenant_id: str, job_id: str) -> bool:
        with self._connect() as conn:
            cursor = self._execute(conn, "DELETE FROM universe_jobs WHERE tenant_id = ? AND job_id = ?", (tenant_id, job_id))
            return cursor.rowcount > 0

    def summarize_jobs(self, *, tenant_id: str, universe_id: Optional[str] = None) -> Dict[str, Any]:
        clauses = ["tenant_id = ?"]
        params: List[Any] = [tenant_id]
        if universe_id:
            clauses.append("universe_id = ?"); params.append(universe_id)
        where_sql = " AND ".join(clauses)
        with self._connect() as conn:
            status_rows = self._execute(conn, f"SELECT status, COUNT(*) AS count FROM universe_jobs WHERE {where_sql} GROUP BY status", params).fetchall()
            type_rows = self._execute(conn, f"SELECT job_type, COUNT(*) AS count FROM universe_jobs WHERE {where_sql} GROUP BY job_type", params).fetchall()
            priority_rows = self._execute(conn, f"SELECT priority, COUNT(*) AS count FROM universe_jobs WHERE {where_sql} GROUP BY priority", params).fetchall()
            total = self._execute(conn, f"SELECT COUNT(*) AS count FROM universe_jobs WHERE {where_sql}", params).fetchone()["count"]
        return {
            "tenant_id": tenant_id,
            "universe_id": universe_id,
            "total_jobs": total,
            "by_status": {row["status"]: row["count"] for row in status_rows},
            "by_type": {row["job_type"]: row["count"] for row in type_rows},
            "by_priority": {row["priority"]: row["count"] for row in priority_rows},
            "generated_at": utc_now_iso(),
        }

    @staticmethod
    def _insert_job_sql() -> str:
        return """
            INSERT INTO universe_jobs (
                job_id, tenant_id, universe_id, job_type, status, priority,
                provider, symbol, payload_json, result_ref, error_message,
                attempt_count, max_attempts, created_by, created_at,
                updated_at, queued_at, started_at, completed_at,
                cancelled_at, correlation_id, tags_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    @staticmethod
    def _insert_event_sql() -> str:
        return """
            INSERT INTO universe_job_events (
                event_id, job_id, tenant_id, event_type,
                message, payload_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """

    @staticmethod
    def _job_insert_tuple(job: UniverseJob) -> tuple[Any, ...]:
        return (
            job.job_id, job.tenant_id, job.universe_id, job.job_type, job.status, job.priority,
            job.provider, job.symbol, _json_dumps(job.payload), job.result_ref, job.error_message,
            job.attempt_count, job.max_attempts, job.created_by, job.created_at, job.updated_at,
            job.queued_at, job.started_at, job.completed_at, job.cancelled_at, job.correlation_id,
            _json_dumps(job.tags),
        )

    def _insert_job_conn(self, conn: sqlite3.Connection, job: UniverseJob) -> None:
        self._execute(conn, self._insert_job_sql(), self._job_insert_tuple(job))

    def _insert_event_conn(self, conn: sqlite3.Connection, *, job_id: str, tenant_id: str, event_type: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._execute(conn, self._insert_event_sql(), (f"ujevt_{uuid.uuid4().hex}", job_id, tenant_id, event_type, message, _json_dumps(payload or {}), utc_now_iso()))

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> UniverseJob:
        return UniverseJob(
            job_id=row["job_id"], tenant_id=row["tenant_id"], universe_id=row["universe_id"],
            job_type=row["job_type"], status=row["status"], priority=row["priority"], provider=row["provider"],
            symbol=row["symbol"], payload=_json_loads(row["payload_json"], {}), result_ref=row["result_ref"],
            error_message=row["error_message"], attempt_count=int(row["attempt_count"]), max_attempts=int(row["max_attempts"]),
            created_by=row["created_by"], created_at=row["created_at"], updated_at=row["updated_at"], queued_at=row["queued_at"],
            started_at=row["started_at"], completed_at=row["completed_at"], cancelled_at=row["cancelled_at"], correlation_id=row["correlation_id"],
            tags=_json_loads(row["tags_json"], []),
        )

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> UniverseJobEvent:
        return UniverseJobEvent(event_id=row["event_id"], job_id=row["job_id"], tenant_id=row["tenant_id"], event_type=row["event_type"], message=row["message"], payload=_json_loads(row["payload_json"], {}), created_at=row["created_at"])


def create_universe_job_registry(db_path: str = DEFAULT_DB_PATH, profiler: Optional[Any] = None) -> UniverseJobRegistry:
    return UniverseJobRegistry(db_path=db_path, profiler=profiler)
