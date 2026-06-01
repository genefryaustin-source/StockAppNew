"""
modules/analytics/universe_runtime_controller.py
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from modules.analytics.universe_execution_queue import (
    QueueLease,
    UniverseExecutionQueue,
)
from modules.analytics.universe_job_registry import (
    UniverseJob,
    UniverseJobRegistry,
    UniverseJobStatus,
)
from modules.analytics.universe_workload_balancer import (
    AnalyticsWorker,
    AnalyticsWorkItem,
    UniverseWorkloadBalancer,
    WorkerState,
    WorkloadPlan,
)


DEFAULT_DB_PATH = "data/analytics_fabric.db"


# =============================================================================
# Helpers
# =============================================================================

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def ensure_parent(path_str: str) -> None:
    path = Path(path_str)
    if path.parent and str(path.parent) not in ("", "."):
        path.parent.mkdir(parents=True, exist_ok=True)


def json_safe(value: Any) -> str:
    import json

    return json.dumps(value or {}, ensure_ascii=False, sort_keys=True, default=str)


def json_load(value: Optional[str], fallback: Any) -> Any:
    import json

    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


# =============================================================================
# Enums
# =============================================================================

class RuntimeControllerState(str, Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    PAUSED = "PAUSED"
    DRAINING = "DRAINING"
    STOPPING = "STOPPING"
    FAILED = "FAILED"


class RuntimeEventType(str, Enum):
    CONTROLLER_STARTED = "CONTROLLER_STARTED"
    CONTROLLER_STOPPED = "CONTROLLER_STOPPED"
    CONTROLLER_PAUSED = "CONTROLLER_PAUSED"
    CONTROLLER_RESUMED = "CONTROLLER_RESUMED"
    CONTROLLER_DEGRADED = "CONTROLLER_DEGRADED"
    WORKER_REGISTERED = "WORKER_REGISTERED"
    WORKER_HEARTBEAT = "WORKER_HEARTBEAT"
    WORKER_STATE_CHANGED = "WORKER_STATE_CHANGED"
    JOB_DISPATCHED = "JOB_DISPATCHED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_FAILED = "JOB_FAILED"
    LEASE_RECOVERED = "LEASE_RECOVERED"
    BALANCER_PLAN_CREATED = "BALANCER_PLAN_CREATED"
    RUNTIME_TICK = "RUNTIME_TICK"


# =============================================================================
# Dataclasses
# =============================================================================

@dataclass(frozen=True)
class RuntimeWorkerRecord:
    worker_id: str
    state: str = WorkerState.ONLINE.value
    tenant_id: Optional[str] = None
    capacity: int = 5
    active_jobs: int = 0
    provider_affinity: List[str] = field(default_factory=list)
    universe_affinity: List[str] = field(default_factory=list)
    supported_job_types: List[str] = field(default_factory=list)
    error_rate: float = 0.0
    avg_runtime_seconds: float = 0.0
    registered_at: str = field(default_factory=utc_now_iso)
    last_heartbeat_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeTickResult:
    controller_id: str
    state: str
    recovered_leases: int = 0
    queued_jobs_seen: int = 0
    workers_seen: int = 0
    assignments_created: int = 0
    leases_claimed: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    generated_at: str = field(default_factory=utc_now_iso)
    plan: Optional[Dict[str, Any]] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeEvent:
    event_id: str
    controller_id: str
    event_type: str
    message: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)


# =============================================================================
# Runtime Controller
# =============================================================================

class UniverseRuntimeController:
    """
    Runtime controller for the analytics fabric.

    Responsibilities:
        - Maintain durable worker registry
        - Convert queued registry jobs into work items
        - Ask workload balancer for deterministic assignment plan
        - Claim queue leases for available workers
        - Track worker heartbeats and stale workers
        - Recover expired leases
        - Emit durable runtime events

    Design:
        - No global mutable runtime state
        - Short-lived SQLite connections
        - Explicit dependency injection
        - Queue, registry, and balancer remain separate service-owned boundaries
    """

    def __init__(
        self,
        *,
        registry: UniverseJobRegistry,
        queue: UniverseExecutionQueue,
        balancer: UniverseWorkloadBalancer,
        db_path: str = DEFAULT_DB_PATH,
        controller_id: Optional[str] = None,
        stale_worker_seconds: int = 300,
        max_claims_per_tick: int = 25,
    ) -> None:
        self.registry = registry
        self.queue = queue
        self.balancer = balancer
        self.db_path = db_path
        self.controller_id = controller_id or f"urtc_{uuid.uuid4().hex}"
        self.stale_worker_seconds = max(30, int(stale_worker_seconds))
        self.max_claims_per_tick = max(1, int(max_claims_per_tick))

        ensure_parent(self.db_path)
        self.initialize()

    # =========================================================================
    # DB
    # =========================================================================

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_runtime_controller_state (
                    controller_id TEXT PRIMARY KEY,
                    state TEXT NOT NULL,
                    started_at TEXT,
                    stopped_at TEXT,
                    last_tick_at TEXT,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_runtime_workers (
                    worker_id TEXT PRIMARY KEY,
                    controller_id TEXT,
                    state TEXT NOT NULL,
                    tenant_id TEXT,
                    capacity INTEGER NOT NULL DEFAULT 5,
                    active_jobs INTEGER NOT NULL DEFAULT 0,
                    provider_affinity_json TEXT NOT NULL DEFAULT '[]',
                    universe_affinity_json TEXT NOT NULL DEFAULT '[]',
                    supported_job_types_json TEXT NOT NULL DEFAULT '[]',
                    error_rate REAL NOT NULL DEFAULT 0,
                    avg_runtime_seconds REAL NOT NULL DEFAULT 0,
                    registered_at TEXT NOT NULL,
                    last_heartbeat_at TEXT,
                    metadata_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS universe_runtime_events (
                    event_id TEXT PRIMARY KEY,
                    controller_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_workers_state
                ON universe_runtime_workers (state, last_heartbeat_at)
                """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_runtime_events_controller
                ON universe_runtime_events (controller_id, created_at)
                """
            )

            existing = conn.execute(
                """
                SELECT controller_id
                FROM universe_runtime_controller_state
                WHERE controller_id = ?
                """,
                (self.controller_id,),
            ).fetchone()

            if not existing:
                conn.execute(
                    """
                    INSERT INTO universe_runtime_controller_state (
                        controller_id,
                        state,
                        started_at,
                        stopped_at,
                        last_tick_at,
                        updated_at,
                        metadata_json
                    )
                    VALUES (?, ?, NULL, NULL, NULL, ?, '{}')
                    """,
                    (
                        self.controller_id,
                        RuntimeControllerState.STOPPED.value,
                        utc_now_iso(),
                    ),
                )

    # =========================================================================
    # Controller Lifecycle
    # =========================================================================

    def start(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE universe_runtime_controller_state
                SET state = ?,
                    started_at = ?,
                    stopped_at = NULL,
                    updated_at = ?,
                    metadata_json = ?
                WHERE controller_id = ?
                """,
                (
                    RuntimeControllerState.RUNNING.value,
                    now,
                    now,
                    json_safe(metadata or {}),
                    self.controller_id,
                ),
            )
            self._insert_event_conn(
                conn,
                RuntimeEventType.CONTROLLER_STARTED.value,
                "Universe analytics runtime controller started.",
                metadata or {},
            )

    def stop(self, reason: str = "Stopped by request.") -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE universe_runtime_controller_state
                SET state = ?,
                    stopped_at = ?,
                    updated_at = ?
                WHERE controller_id = ?
                """,
                (
                    RuntimeControllerState.STOPPED.value,
                    now,
                    now,
                    self.controller_id,
                ),
            )
            self._insert_event_conn(
                conn,
                RuntimeEventType.CONTROLLER_STOPPED.value,
                reason,
                {"reason": reason},
            )

    def pause(self, reason: str = "Paused by request.") -> None:
        self._set_controller_state(
            RuntimeControllerState.PAUSED.value,
            RuntimeEventType.CONTROLLER_PAUSED.value,
            reason,
            {"reason": reason},
        )

    def resume(self, reason: str = "Resumed by request.") -> None:
        self._set_controller_state(
            RuntimeControllerState.RUNNING.value,
            RuntimeEventType.CONTROLLER_RESUMED.value,
            reason,
            {"reason": reason},
        )

    def mark_degraded(self, reason: str, payload: Optional[Dict[str, Any]] = None) -> None:
        self._set_controller_state(
            RuntimeControllerState.DEGRADED.value,
            RuntimeEventType.CONTROLLER_DEGRADED.value,
            reason,
            payload or {"reason": reason},
        )

    def get_state(self) -> str:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state
                FROM universe_runtime_controller_state
                WHERE controller_id = ?
                """,
                (self.controller_id,),
            ).fetchone()

        return row["state"] if row else RuntimeControllerState.STOPPED.value

    # =========================================================================
    # Worker Registry
    # =========================================================================

    def register_worker(
        self,
        *,
        worker_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        capacity: int = 5,
        provider_affinity: Optional[List[str]] = None,
        universe_affinity: Optional[List[str]] = None,
        supported_job_types: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> RuntimeWorkerRecord:
        now = utc_now_iso()
        wid = worker_id or f"aworker_{uuid.uuid4().hex}"

        record = RuntimeWorkerRecord(
            worker_id=wid,
            controller_id=self.controller_id if hasattr(RuntimeWorkerRecord, "controller_id") else None,  # ignored by dataclass
        ) if False else RuntimeWorkerRecord(
            worker_id=wid,
            state=WorkerState.ONLINE.value,
            tenant_id=tenant_id,
            capacity=max(1, int(capacity)),
            active_jobs=0,
            provider_affinity=provider_affinity or [],
            universe_affinity=universe_affinity or [],
            supported_job_types=supported_job_types or [],
            registered_at=now,
            last_heartbeat_at=now,
            metadata=metadata or {},
        )

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO universe_runtime_workers (
                    worker_id,
                    controller_id,
                    state,
                    tenant_id,
                    capacity,
                    active_jobs,
                    provider_affinity_json,
                    universe_affinity_json,
                    supported_job_types_json,
                    error_rate,
                    avg_runtime_seconds,
                    registered_at,
                    last_heartbeat_at,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(worker_id) DO UPDATE SET
                    controller_id = excluded.controller_id,
                    state = excluded.state,
                    tenant_id = excluded.tenant_id,
                    capacity = excluded.capacity,
                    provider_affinity_json = excluded.provider_affinity_json,
                    universe_affinity_json = excluded.universe_affinity_json,
                    supported_job_types_json = excluded.supported_job_types_json,
                    last_heartbeat_at = excluded.last_heartbeat_at,
                    metadata_json = excluded.metadata_json
                """,
                (
                    record.worker_id,
                    self.controller_id,
                    record.state,
                    record.tenant_id,
                    record.capacity,
                    record.active_jobs,
                    json_safe(record.provider_affinity),
                    json_safe(record.universe_affinity),
                    json_safe(record.supported_job_types),
                    record.error_rate,
                    record.avg_runtime_seconds,
                    record.registered_at,
                    record.last_heartbeat_at,
                    json_safe(record.metadata),
                ),
            )
            self._insert_event_conn(
                conn,
                RuntimeEventType.WORKER_REGISTERED.value,
                "Analytics runtime worker registered.",
                asdict(record),
            )

        return record

    def worker_heartbeat(
        self,
        *,
        worker_id: str,
        active_jobs: Optional[int] = None,
        capacity: Optional[int] = None,
        error_rate: Optional[float] = None,
        avg_runtime_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        now = utc_now_iso()

        set_parts = [
            "state = ?",
            "last_heartbeat_at = ?",
        ]
        params: List[Any] = [WorkerState.ONLINE.value, now]

        if active_jobs is not None:
            set_parts.append("active_jobs = ?")
            params.append(max(0, int(active_jobs)))

        if capacity is not None:
            set_parts.append("capacity = ?")
            params.append(max(1, int(capacity)))

        if error_rate is not None:
            set_parts.append("error_rate = ?")
            params.append(max(0.0, min(1.0, float(error_rate))))

        if avg_runtime_seconds is not None:
            set_parts.append("avg_runtime_seconds = ?")
            params.append(max(0.0, float(avg_runtime_seconds)))

        if metadata is not None:
            set_parts.append("metadata_json = ?")
            params.append(json_safe(metadata))

        params.append(worker_id)

        with self._connect() as conn:
            cur = conn.execute(
                f"""
                UPDATE universe_runtime_workers
                SET {", ".join(set_parts)}
                WHERE worker_id = ?
                """,
                params,
            )

            if cur.rowcount > 0:
                self._insert_event_conn(
                    conn,
                    RuntimeEventType.WORKER_HEARTBEAT.value,
                    "Analytics worker heartbeat received.",
                    {
                        "worker_id": worker_id,
                        "active_jobs": active_jobs,
                        "capacity": capacity,
                        "error_rate": error_rate,
                        "avg_runtime_seconds": avg_runtime_seconds,
                    },
                )
                return True

        return False

    def set_worker_state(
        self,
        *,
        worker_id: str,
        state: str | WorkerState,
        reason: str = "Worker state updated.",
    ) -> bool:
        next_state = state.value if isinstance(state, WorkerState) else str(state).upper()

        with self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE universe_runtime_workers
                SET state = ?
                WHERE worker_id = ?
                """,
                (next_state, worker_id),
            )

            if cur.rowcount > 0:
                self._insert_event_conn(
                    conn,
                    RuntimeEventType.WORKER_STATE_CHANGED.value,
                    reason,
                    {"worker_id": worker_id, "state": next_state, "reason": reason},
                )
                return True

        return False

    def list_workers(
        self,
        *,
        state: Optional[str | WorkerState] = None,
        tenant_id: Optional[str] = None,
    ) -> List[RuntimeWorkerRecord]:
        clauses: List[str] = []
        params: List[Any] = []

        if state:
            clauses.append("state = ?")
            params.append(state.value if isinstance(state, WorkerState) else str(state).upper())

        if tenant_id:
            clauses.append("tenant_id = ?")
            params.append(tenant_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM universe_runtime_workers
                {where_sql}
                ORDER BY registered_at ASC
                """,
                params,
            ).fetchall()

        return [self._row_to_worker_record(row) for row in rows]

    def mark_stale_workers(self) -> int:
        cutoff = utc_now() - timedelta(seconds=self.stale_worker_seconds)
        count = 0

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT worker_id
                FROM universe_runtime_workers
                WHERE state = ?
                AND last_heartbeat_at IS NOT NULL
                AND last_heartbeat_at < ?
                """,
                (WorkerState.ONLINE.value, cutoff.isoformat()),
            ).fetchall()

            for row in rows:
                conn.execute(
                    """
                    UPDATE universe_runtime_workers
                    SET state = ?
                    WHERE worker_id = ?
                    """,
                    (WorkerState.OFFLINE.value, row["worker_id"]),
                )
                self._insert_event_conn(
                    conn,
                    RuntimeEventType.WORKER_STATE_CHANGED.value,
                    "Analytics worker marked offline due to stale heartbeat.",
                    {"worker_id": row["worker_id"], "reason": "stale_heartbeat"},
                )
                count += 1

        return count

    # =========================================================================
    # Runtime Tick / Planning
    # =========================================================================

    def tick(
        self,
        *,
        tenant_id: Optional[str] = None,
        universe_id: Optional[str] = None,
        execute_callback: Optional[Callable[[UniverseJob, QueueLease], Dict[str, Any]]] = None,
    ) -> RuntimeTickResult:
        state = self.get_state()
        if state not in {
            RuntimeControllerState.RUNNING.value,
            RuntimeControllerState.DEGRADED.value,
        }:
            return RuntimeTickResult(
                controller_id=self.controller_id,
                state=state,
                metrics={"skipped": True, "reason": "controller_not_running"},
            )

        recovered = self.queue.recover_expired_leases()
        stale_workers = self.mark_stale_workers()

        workers = self._workers_for_balancer(tenant_id=tenant_id)
        queued_jobs = self._queued_jobs_for_balancer(
            tenant_id=tenant_id,
            universe_id=universe_id,
        )

        plan = self.balancer.build_plan(
            workers=workers,
            queued_jobs=queued_jobs,
        )

        claims: List[QueueLease] = []
        completed_jobs = 0
        failed_jobs = 0

        for assignment in plan.assignments[: self.max_claims_per_tick]:
            if not assignment.worker_id:
                continue

            lease = self.queue.claim_next_job(worker_id=assignment.worker_id)
            if not lease:
                continue

            claims.append(lease)

            self._increment_worker_active_jobs(assignment.worker_id, 1)

            self._emit_event(
                RuntimeEventType.JOB_DISPATCHED.value,
                "Analytics job dispatched to worker.",
                {
                    "job_id": lease.job_id,
                    "tenant_id": lease.tenant_id,
                    "worker_id": lease.worker_id,
                    "lease_id": lease.lease_id,
                    "assignment": asdict(assignment),
                },
            )

            if execute_callback:
                job = self.registry.get_job(
                    tenant_id=lease.tenant_id,
                    job_id=lease.job_id,
                )

                if not job:
                    self.queue.fail_job(
                        lease_id=lease.lease_id,
                        error_message="Claimed job was not found in registry.",
                    )
                    failed_jobs += 1
                    self._increment_worker_active_jobs(assignment.worker_id, -1)
                    continue

                try:
                    result = execute_callback(job, lease) or {}
                    result_ref = result.get("result_ref")

                    self.queue.complete_job(
                        lease_id=lease.lease_id,
                        result_ref=result_ref,
                    )
                    completed_jobs += 1

                    self._emit_event(
                        RuntimeEventType.JOB_COMPLETED.value,
                        "Analytics job completed by runtime callback.",
                        {
                            "job_id": lease.job_id,
                            "tenant_id": lease.tenant_id,
                            "worker_id": lease.worker_id,
                            "result": result,
                        },
                    )

                except Exception as exc:
                    self.queue.fail_job(
                        lease_id=lease.lease_id,
                        error_message=str(exc),
                    )
                    failed_jobs += 1

                    self._emit_event(
                        RuntimeEventType.JOB_FAILED.value,
                        "Analytics job failed during runtime callback.",
                        {
                            "job_id": lease.job_id,
                            "tenant_id": lease.tenant_id,
                            "worker_id": lease.worker_id,
                            "error": str(exc),
                        },
                    )

                finally:
                    self._increment_worker_active_jobs(assignment.worker_id, -1)

        now = utc_now_iso()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE universe_runtime_controller_state
                SET last_tick_at = ?,
                    updated_at = ?
                WHERE controller_id = ?
                """,
                (now, now, self.controller_id),
            )
            self._insert_event_conn(
                conn,
                RuntimeEventType.RUNTIME_TICK.value,
                "Universe analytics runtime tick completed.",
                {
                    "recovered_leases": recovered,
                    "stale_workers": stale_workers,
                    "queued_jobs_seen": len(queued_jobs),
                    "workers_seen": len(workers),
                    "assignments_created": len(plan.assignments),
                    "leases_claimed": len(claims),
                    "completed_jobs": completed_jobs,
                    "failed_jobs": failed_jobs,
                    "plan_decision": plan.decision,
                },
            )

        return RuntimeTickResult(
            controller_id=self.controller_id,
            state=state,
            recovered_leases=recovered,
            queued_jobs_seen=len(queued_jobs),
            workers_seen=len(workers),
            assignments_created=len(plan.assignments),
            leases_claimed=len(claims),
            completed_jobs=completed_jobs,
            failed_jobs=failed_jobs,
            plan=self._plan_to_dict(plan),
            metrics={
                "stale_workers_marked_offline": stale_workers,
                "queue_metrics": self.queue.queue_metrics(),
            },
        )

    # =========================================================================
    # Queued Job Discovery
    # =========================================================================

    def enqueue_registered_jobs(
        self,
        *,
        tenant_id: str,
        universe_id: Optional[str] = None,
        limit: int = 250,
    ) -> int:
        jobs = self.registry.list_jobs(
            tenant_id=tenant_id,
            universe_id=universe_id,
            status=UniverseJobStatus.REGISTERED,
            limit=limit,
        )

        count = 0
        for job in jobs:
            if self.queue.enqueue_job(
                tenant_id=job.tenant_id,
                job_id=job.job_id,
                priority=job.priority,
            ):
                count += 1

        return count

    def promote_retry_jobs(
        self,
        *,
        tenant_id: str,
        universe_id: Optional[str] = None,
        limit: int = 250,
    ) -> int:
        jobs = self.registry.list_jobs(
            tenant_id=tenant_id,
            universe_id=universe_id,
            status=UniverseJobStatus.RETRY_PENDING,
            limit=limit,
        )

        count = 0
        for job in jobs:
            if self.queue.enqueue_job(
                tenant_id=job.tenant_id,
                job_id=job.job_id,
                priority=job.priority,
                delay_seconds=0,
            ):
                count += 1

        return count

    # =========================================================================
    # Events / Metrics
    # =========================================================================

    def list_events(self, limit: int = 250) -> List[RuntimeEvent]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM universe_runtime_events
                WHERE controller_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (self.controller_id, max(1, int(limit))),
            ).fetchall()

        return [
            RuntimeEvent(
                event_id=row["event_id"],
                controller_id=row["controller_id"],
                event_type=row["event_type"],
                message=row["message"],
                payload=json_load(row["payload_json"], {}),
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def runtime_metrics(self) -> Dict[str, Any]:
        workers = self.list_workers()
        queue_metrics = self.queue.queue_metrics()

        online = [w for w in workers if w.state == WorkerState.ONLINE.value]
        degraded = [w for w in workers if w.state == WorkerState.DEGRADED.value]
        offline = [w for w in workers if w.state == WorkerState.OFFLINE.value]
        draining = [w for w in workers if w.state == WorkerState.DRAINING.value]

        total_capacity = sum(w.capacity for w in online)
        active_jobs = sum(w.active_jobs for w in online)

        return {
            "controller_id": self.controller_id,
            "state": self.get_state(),
            "workers_total": len(workers),
            "workers_online": len(online),
            "workers_degraded": len(degraded),
            "workers_offline": len(offline),
            "workers_draining": len(draining),
            "total_capacity": total_capacity,
            "active_jobs": active_jobs,
            "available_capacity": max(0, total_capacity - active_jobs),
            "queue": queue_metrics,
            "generated_at": utc_now_iso(),
        }

    # =========================================================================
    # Internal
    # =========================================================================

    def _queued_jobs_for_balancer(
        self,
        *,
        tenant_id: Optional[str],
        universe_id: Optional[str],
    ) -> List[AnalyticsWorkItem]:
        tenant_ids = [tenant_id] if tenant_id else self._known_tenant_ids()

        work_items: List[AnalyticsWorkItem] = []

        for tid in tenant_ids:
            jobs = self.registry.list_jobs(
                tenant_id=tid,
                universe_id=universe_id,
                status=UniverseJobStatus.QUEUED,
                limit=500,
            )

            for job in jobs:
                work_items.append(
                    AnalyticsWorkItem(
                        job_id=job.job_id,
                        tenant_id=job.tenant_id,
                        universe_id=job.universe_id,
                        job_type=job.job_type,
                        priority=job.priority,
                        provider=job.provider,
                        symbol=job.symbol,
                        estimated_runtime_seconds=job.payload.get(
                            "estimated_runtime_seconds"
                        ),
                        metadata={
                            "correlation_id": job.correlation_id,
                            "tags": job.tags,
                        },
                    )
                )

        return work_items

    def _workers_for_balancer(
        self,
        *,
        tenant_id: Optional[str],
    ) -> List[AnalyticsWorker]:
        records = self.list_workers()

        workers: List[AnalyticsWorker] = []

        for record in records:
            if record.state != WorkerState.ONLINE.value:
                continue

            if tenant_id and record.tenant_id and record.tenant_id != tenant_id:
                continue

            workers.append(
                AnalyticsWorker(
                    worker_id=record.worker_id,
                    tenant_id=record.tenant_id,
                    state=record.state,
                    capacity=record.capacity,
                    active_jobs=record.active_jobs,
                    provider_affinity=record.provider_affinity,
                    universe_affinity=record.universe_affinity,
                    supported_job_types=record.supported_job_types,
                    error_rate=record.error_rate,
                    avg_runtime_seconds=record.avg_runtime_seconds,
                    last_heartbeat_at=record.last_heartbeat_at,
                    metadata=record.metadata,
                )
            )

        return workers

    def _known_tenant_ids(self) -> List[str]:
        with self._connect() as conn:
            worker_rows = conn.execute(
                """
                SELECT DISTINCT tenant_id
                FROM universe_runtime_workers
                WHERE tenant_id IS NOT NULL
                """
            ).fetchall()

            job_rows = conn.execute(
                """
                SELECT DISTINCT tenant_id
                FROM universe_jobs
                """
            ).fetchall()

        tenant_ids = {
            row["tenant_id"]
            for row in worker_rows + job_rows
            if row["tenant_id"]
        }

        return sorted(tenant_ids)

    def _increment_worker_active_jobs(self, worker_id: str, delta: int) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE universe_runtime_workers
                SET active_jobs = MAX(0, active_jobs + ?)
                WHERE worker_id = ?
                """,
                (int(delta), worker_id),
            )

    def _set_controller_state(
        self,
        state: str,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = utc_now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE universe_runtime_controller_state
                SET state = ?,
                    updated_at = ?
                WHERE controller_id = ?
                """,
                (state, now, self.controller_id),
            )
            self._insert_event_conn(
                conn,
                event_type,
                message,
                payload or {},
            )

    def _emit_event(
        self,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._connect() as conn:
            self._insert_event_conn(
                conn,
                event_type,
                message,
                payload or {},
            )

    def _insert_event_conn(
        self,
        conn: sqlite3.Connection,
        event_type: str,
        message: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO universe_runtime_events (
                event_id,
                controller_id,
                event_type,
                message,
                payload_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                f"urtevt_{uuid.uuid4().hex}",
                self.controller_id,
                event_type,
                message,
                json_safe(payload or {}),
                utc_now_iso(),
            ),
        )

    @staticmethod
    def _row_to_worker_record(row: sqlite3.Row) -> RuntimeWorkerRecord:
        return RuntimeWorkerRecord(
            worker_id=row["worker_id"],
            state=row["state"],
            tenant_id=row["tenant_id"],
            capacity=int(row["capacity"]),
            active_jobs=int(row["active_jobs"]),
            provider_affinity=json_load(row["provider_affinity_json"], []),
            universe_affinity=json_load(row["universe_affinity_json"], []),
            supported_job_types=json_load(row["supported_job_types_json"], []),
            error_rate=float(row["error_rate"]),
            avg_runtime_seconds=float(row["avg_runtime_seconds"]),
            registered_at=row["registered_at"],
            last_heartbeat_at=row["last_heartbeat_at"],
            metadata=json_load(row["metadata_json"], {}),
        )

    @staticmethod
    def _plan_to_dict(plan: WorkloadPlan) -> Dict[str, Any]:
        return {
            "decision": plan.decision,
            "assignments": [asdict(a) for a in plan.assignments],
            "held_jobs": plan.held_jobs,
            "scale_recommendation": plan.scale_recommendation,
            "generated_at": plan.generated_at,
            "metrics": plan.metrics,
        }


# =============================================================================
# Factory
# =============================================================================

def create_universe_runtime_controller(
    *,
    registry: UniverseJobRegistry,
    queue: UniverseExecutionQueue,
    balancer: UniverseWorkloadBalancer,
    db_path: str = DEFAULT_DB_PATH,
    controller_id: Optional[str] = None,
    stale_worker_seconds: int = 300,
    max_claims_per_tick: int = 25,
) -> UniverseRuntimeController:
    return UniverseRuntimeController(
        registry=registry,
        queue=queue,
        balancer=balancer,
        db_path=db_path,
        controller_id=controller_id,
        stale_worker_seconds=stale_worker_seconds,
        max_claims_per_tick=max_claims_per_tick,
    )