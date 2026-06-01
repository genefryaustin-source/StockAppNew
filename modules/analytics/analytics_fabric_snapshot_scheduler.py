"""
modules/analytics/analytics_fabric_snapshot_scheduler.py
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional


SNAPSHOT_CONTROL_TOWER = "CONTROL_TOWER"
SNAPSHOT_EXECUTIVE = "EXECUTIVE"
SNAPSHOT_VALIDATION = "VALIDATION"
SNAPSHOT_STRESS = "STRESS"
SNAPSHOT_BENCHMARK = "BENCHMARK"
SNAPSHOT_CAPACITY = "CAPACITY"
SNAPSHOT_PROVIDER = "PROVIDER"
SNAPSHOT_GOVERNANCE = "GOVERNANCE"
SNAPSHOT_GLOBAL_PLAN = "GLOBAL_PLAN"
SNAPSHOT_TENANT_INTELLIGENCE = "TENANT_INTELLIGENCE"
SNAPSHOT_FABRIC_HEALTH = "FABRIC_HEALTH"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


@dataclass
class SnapshotSchedule:
    job_id: str
    snapshot_type: str
    interval_seconds: int
    enabled: bool = True
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: str = field(default_factory=utc_now_iso)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotExecution:
    execution_id: str
    job_id: str
    snapshot_type: str
    status: str
    runtime_ms: float
    snapshot_id: Optional[str]
    started_at: str
    completed_at: str
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotResult:
    snapshot_id: str
    snapshot_type: str
    status: str
    payload_size: int
    created_at: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SnapshotStatistics:
    jobs_registered: int = 0
    jobs_executed: int = 0
    jobs_failed: int = 0
    snapshots_created: int = 0
    average_runtime_ms: float = 0.0
    last_execution_time: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AnalyticsFabricSnapshotScheduler:
    def __init__(
        self,
        persistence_engine,
        analytics_fabric=None,
        max_history_records: int = 10000,
        retention_days: int = 365,
    ):
        self.persistence_engine = persistence_engine
        self.analytics_fabric = analytics_fabric

        self.max_history_records = max_history_records
        self.retention_days = retention_days

        self.jobs: Dict[str, SnapshotSchedule] = {}
        self.execution_log: List[SnapshotExecution] = []

        self.stats = SnapshotStatistics()

    def register_snapshot_job(
        self,
        snapshot_type: str,
        interval_seconds: int,
        enabled: bool = True,
    ) -> str:
        job_id = f"snapjob_{uuid.uuid4().hex}"

        now = utc_now()

        schedule = SnapshotSchedule(
            job_id=job_id,
            snapshot_type=snapshot_type,
            interval_seconds=interval_seconds,
            enabled=enabled,
            next_run_at=(
                now + timedelta(seconds=interval_seconds)
            ).isoformat(),
        )

        self.jobs[job_id] = schedule

        self.stats.jobs_registered = len(self.jobs)

        return job_id

    def remove_snapshot_job(
        self,
        job_id: str,
    ) -> bool:
        if job_id not in self.jobs:
            return False

        del self.jobs[job_id]

        self.stats.jobs_registered = len(self.jobs)

        return True

    def pause_snapshot_job(
        self,
        job_id: str,
    ) -> bool:
        job = self.jobs.get(job_id)

        if not job:
            return False

        job.enabled = False

        return True

    def resume_snapshot_job(
        self,
        job_id: str,
    ) -> bool:
        job = self.jobs.get(job_id)

        if not job:
            return False

        job.enabled = True

        return True

    def run_snapshot_cycle(self) -> Dict[str, Any]:
        now = utc_now()

        executed = []

        for job in self.jobs.values():

            if not job.enabled:
                continue

            if not job.next_run_at:
                continue

            next_run = datetime.fromisoformat(
                job.next_run_at
            )

            if next_run <= now:
                executed.append(
                    self.run_snapshot_job(job.job_id)
                )

        return {
            "jobs_evaluated": len(self.jobs),
            "jobs_executed": len(executed),
            "executions": executed,
            "generated_at": utc_now_iso(),
        }

    def run_all_snapshots(self) -> Dict[str, Any]:
        results = []

        for job_id in list(self.jobs.keys()):
            results.append(
                self.run_snapshot_job(job_id)
            )

        return {
            "jobs_executed": len(results),
            "results": results,
            "generated_at": utc_now_iso(),
        }

    def run_snapshot_job(
        self,
        job_id: str,
    ) -> Dict[str, Any]:
        job = self.jobs.get(job_id)

        if not job:
            raise ValueError(
                f"Snapshot job not found: {job_id}"
            )

        started = utc_now()
        start_time = time.perf_counter()

        execution_id = (
            f"exec_{uuid.uuid4().hex}"
        )

        try:
            snapshot_id = self._create_snapshot(
                job.snapshot_type
            )

            runtime_ms = (
                time.perf_counter() - start_time
            ) * 1000

            execution = SnapshotExecution(
                execution_id=execution_id,
                job_id=job.job_id,
                snapshot_type=job.snapshot_type,
                status="SUCCESS",
                runtime_ms=runtime_ms,
                snapshot_id=snapshot_id,
                started_at=started.isoformat(),
                completed_at=utc_now_iso(),
            )

            self.execution_log.append(execution)

            self.stats.jobs_executed += 1
            self.stats.snapshots_created += 1
            self.stats.last_execution_time = (
                utc_now_iso()
            )

            self._update_runtime_average(
                runtime_ms
            )

            job.last_run_at = utc_now_iso()

            job.next_run_at = (
                utc_now()
                + timedelta(
                    seconds=job.interval_seconds
                )
            ).isoformat()

            return execution.as_dict()

        except Exception as exc:

            runtime_ms = (
                time.perf_counter() - start_time
            ) * 1000

            execution = SnapshotExecution(
                execution_id=execution_id,
                job_id=job.job_id,
                snapshot_type=job.snapshot_type,
                status="FAILED",
                runtime_ms=runtime_ms,
                snapshot_id=None,
                started_at=started.isoformat(),
                completed_at=utc_now_iso(),
                error=str(exc),
            )

            self.execution_log.append(execution)

            self.stats.jobs_failed += 1

            return execution.as_dict()

    def _create_snapshot(
        self,
        snapshot_type: str,
    ) -> str:

        payload = self._collect_snapshot_payload(
            snapshot_type
        )

        if snapshot_type == SNAPSHOT_CONTROL_TOWER:
            return self.persistence_engine.save_control_tower_snapshot(
                payload
            )

        if snapshot_type == SNAPSHOT_EXECUTIVE:
            return self.persistence_engine.save_executive_snapshot(
                "executive_snapshot",
                payload,
            )

        if snapshot_type == SNAPSHOT_CAPACITY:
            return self.persistence_engine.save_capacity_forecast(
                "scheduled_capacity",
                payload,
            )

        if snapshot_type == SNAPSHOT_PROVIDER:
            return self.persistence_engine.save_provider_profile(
                payload.get(
                    "provider",
                    "ALL_PROVIDERS",
                ),
                payload,
            )

        if snapshot_type == SNAPSHOT_GOVERNANCE:
            return self.persistence_engine.save_governance_decision(
                "scheduled_governance",
                "INFO",
                payload,
            )

        if snapshot_type == SNAPSHOT_GLOBAL_PLAN:
            return self.persistence_engine.save_global_plan(
                payload.get(
                    "plan_id",
                    f"plan_{uuid.uuid4().hex}",
                ),
                payload.get(
                    "state",
                    "ACTIVE",
                ),
                payload,
            )

        if snapshot_type == SNAPSHOT_TENANT_INTELLIGENCE:
            return self.persistence_engine.save_tenant_intelligence(
                payload.get(
                    "tenant_id",
                    "ALL_TENANTS",
                ),
                payload,
            )

        if snapshot_type == SNAPSHOT_FABRIC_HEALTH:
            return self.persistence_engine.save_fabric_health_snapshot(
                payload
            )

        if snapshot_type == SNAPSHOT_VALIDATION:
            return self.persistence_engine.save_validation_result(
                "scheduled_validation",
                payload,
            )

        if snapshot_type == SNAPSHOT_STRESS:
            return self.persistence_engine.save_stress_result(
                "scheduled_stress",
                payload,
                0.0,
            )

        if snapshot_type == SNAPSHOT_BENCHMARK:
            return self.persistence_engine.save_benchmark_result(
                "scheduled_benchmark",
                payload.get(
                    "ops_per_second",
                    0.0,
                ),
                payload,
            )

        raise ValueError(
            f"Unsupported snapshot type: {snapshot_type}"
        )

    def _collect_snapshot_payload(
        self,
        snapshot_type: str,
    ) -> Dict[str, Any]:

        if self.analytics_fabric is None:
            return {
                "snapshot_type": snapshot_type,
                "generated_at": utc_now_iso(),
            }

        fabric = self.analytics_fabric

        if snapshot_type == SNAPSHOT_CONTROL_TOWER:
            return {
                "fabric_summary": getattr(
                    fabric,
                    "summary",
                    lambda: {},
                )(),
                "generated_at": utc_now_iso(),
            }

        if snapshot_type == SNAPSHOT_EXECUTIVE:
            return {
                "fabric_summary": getattr(
                    fabric,
                    "summary",
                    lambda: {},
                )(),
                "generated_at": utc_now_iso(),
            }

        if snapshot_type == SNAPSHOT_CAPACITY:
            return getattr(
                fabric.worker_capacity_model,
                "capacity_summary",
                lambda: {},
            )()

        if snapshot_type == SNAPSHOT_PROVIDER:
            return getattr(
                fabric.provider_cost_intelligence,
                "summary",
                lambda: {},
            )()

        if snapshot_type == SNAPSHOT_GOVERNANCE:
            return getattr(
                fabric.execution_governor,
                "governance_summary",
                lambda: {},
            )()

        if snapshot_type == SNAPSHOT_GLOBAL_PLAN:
            return getattr(
                fabric.global_planner,
                "planner_summary",
                lambda: {},
            )()

        if snapshot_type == SNAPSHOT_TENANT_INTELLIGENCE:
            return getattr(
                fabric.tenant_universe_intelligence,
                "intelligence_summary",
                lambda: {},
            )()

        if snapshot_type == SNAPSHOT_FABRIC_HEALTH:
            return {
                "runtime": getattr(
                    fabric.runtime_controller,
                    "runtime_metrics",
                    lambda: {},
                )(),
                "queue": getattr(
                    fabric.execution_queue,
                    "queue_metrics",
                    lambda: {},
                )(),
                "generated_at": utc_now_iso(),
            }

        return {
            "snapshot_type": snapshot_type,
            "generated_at": utc_now_iso(),
        }

    def cleanup_expired_snapshots(self) -> Dict[str, Any]:
        return {
            "status": "NOT_IMPLEMENTED",
            "retention_days": self.retention_days,
            "generated_at": utc_now_iso(),
        }

    def archive_old_snapshots(self) -> Dict[str, Any]:
        return {
            "status": "NOT_IMPLEMENTED",
            "generated_at": utc_now_iso(),
        }

    def snapshot_summary(self) -> Dict[str, Any]:
        return {
            **self.stats.as_dict(),
            "registered_jobs": len(self.jobs),
            "execution_history": len(
                self.execution_log
            ),
            "generated_at": utc_now_iso(),
        }

    def snapshot_health(self) -> Dict[str, Any]:
        success = len(
            [
                e
                for e in self.execution_log
                if e.status == "SUCCESS"
            ]
        )

        failed = len(
            [
                e
                for e in self.execution_log
                if e.status == "FAILED"
            ]
        )

        total = success + failed

        success_rate = (
            success / total
            if total
            else 1.0
        )

        return {
            "success_rate": round(
                success_rate * 100,
                2,
            ),
            "successful_executions": success,
            "failed_executions": failed,
            "total_executions": total,
            "generated_at": utc_now_iso(),
        }

    def execution_history(
        self,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        return [
            execution.as_dict()
            for execution in self.execution_log[-limit:]
        ]

    def job_registry(self) -> List[Dict[str, Any]]:
        return [
            job.as_dict()
            for job in self.jobs.values()
        ]

    def register_default_snapshot_jobs(
        self,
        interval_seconds: int = 3600,
    ) -> Dict[str, str]:

        jobs = {}

        for snapshot_type in [
            SNAPSHOT_CONTROL_TOWER,
            SNAPSHOT_EXECUTIVE,
            SNAPSHOT_CAPACITY,
            SNAPSHOT_PROVIDER,
            SNAPSHOT_GOVERNANCE,
            SNAPSHOT_GLOBAL_PLAN,
            SNAPSHOT_TENANT_INTELLIGENCE,
            SNAPSHOT_FABRIC_HEALTH,
        ]:
            jobs[snapshot_type] = (
                self.register_snapshot_job(
                    snapshot_type=snapshot_type,
                    interval_seconds=interval_seconds,
                )
            )

        return jobs

    def _update_runtime_average(
        self,
        runtime_ms: float,
    ) -> None:

        total = self.stats.jobs_executed

        if total <= 1:
            self.stats.average_runtime_ms = (
                runtime_ms
            )
            return

        self.stats.average_runtime_ms = (
            (
                self.stats.average_runtime_ms
                * (total - 1)
            )
            + runtime_ms
        ) / total